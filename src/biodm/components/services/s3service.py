from typing import List, Any, Sequence, Dict

from sqlalchemy import Insert
from sqlalchemy.ext.asyncio import AsyncSession


from biodm.components.table import Base, S3File
from biodm.exceptions import FailedRead
from biodm.managers import DatabaseManager, S3Manager
from biodm.utils.utils import utcnow
from biodm.utils.security import UserInfo
from .dbservice import UnaryEntityService


class S3Service(UnaryEntityService):
    """Class that manages AWS S3 bucket transactions.
    Automatically associated with files entities which in principle should be unary."""
    @property
    def s3(self) -> S3Manager:
        return self.app.s3

    def callback(self, item):
        mapping = { # Map primary key values to route elements.
            key: getattr(item, key)
            for key in self.table.pk()
        }

        route = str(self.table.ctrl.route_upload_callback)
        for key, val in mapping.items():
            route = route.replace("{" + f"{key}" + "}", str(val))

        srv = self.app.server_endpoint.strip('/')
        return f"{srv}{route}"

    async def gen_key(self, item, session: AsyncSession):
        await session.refresh(item, ['key_salt', 'filename', 'extension'])
        version = ""
        if self.table.is_versioned():
            await session.refresh(item, ['version'])
            version = "_"+str(item.version)

        return f"{item.key_salt}_{item.filename}{version}.{item.extension}"

    async def gen_upload_form(self, item, session: AsyncSession):
        assert isinstance(item, S3File) # mypy.

        item.upload_form = str(self.s3.create_presigned_post(
            object_name=await self.gen_key(item, session=session),
            callback=self.callback(item)
        ))

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT special case for file: populate url after getting entity id."""
        item = await super()._insert(stmt, session=session)
        await self.gen_upload_form(item, session=session)
        return item

    @DatabaseManager.in_session
    async def _insert_list(self, stmts: Sequence[Insert], session: AsyncSession) -> Sequence[Base]:
        """INSERT many objects into the DB database, check token write permission before commit."""
        items = await super()._insert_list(stmts, session=session)
        for item in items:
            await self.gen_upload_form(item, session=session)
        return items

    @DatabaseManager.in_session
    async def upload_success(self, pk_val, session: AsyncSession):
        file = await self.read(pk_val, fields=['ready', 'upload_form'], session=session)
        file.validated_at = utcnow()
        file.ready = True
        file.upload_form = ""

    @DatabaseManager.in_session
    async def download(self, pk_val: List[Any], user_info: UserInfo | None, session: AsyncSession):
        # File management.
        fields = ['filename', 'extension', 'dl_count', 'ready', 'key_salt']
        # Also fetch foreign keys, as they may be necessary for permission check.
        fields += list(c.name for c in self.table.__table__.columns if c.foreign_keys)
        file = await self.read(pk_val, fields=fields, session=session)

        assert isinstance(file, S3File) # mypy.

        await self._check_permissions("download", user_info, file.__dict__, session=session)

        if not file.ready:
            raise FailedRead() # TODO: better error ?

        url = self.s3.create_presigned_download_url(await self.gen_key(file, session=session))
        file.dl_count += 1
        return url

    @DatabaseManager.in_session
    async def release(
        self,
        pk_val: List[Any],
        fields: List[str],
        update: Dict[str, Any],
        session: AsyncSession,
        user_info: UserInfo | None = None,
    ) -> Base:
        item = await super().release(
            pk_val=pk_val,
            fields=fields,
            update=update,
            session=session,
            user_info=user_info
        )
        item.created_at = utcnow()
        item.validated_at = None
        item.ready = False
        item.dl_count = 0
        await self.gen_upload_form(item, session=session)
        return item
