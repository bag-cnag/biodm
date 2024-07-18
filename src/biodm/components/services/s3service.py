from typing import List, Any, Sequence

from sqlalchemy import Insert
from sqlalchemy.ext.asyncio import AsyncSession


from biodm.components.table import Base, S3File
from biodm.managers import DatabaseManager, S3Manager
from biodm.utils.utils import to_it
from biodm.utils.security import UserInfo
from .dbservice import UnaryEntityService


class S3Service(UnaryEntityService):
    """Class that manages AWS S3 bucket transactions.
    Automatically associated with files entities which in principle should be unary."""
    @property
    def s3(self) -> S3Manager:
        return self.app.s3

    @classmethod
    def callback(cls, id):
        return f"{cls.app.server_endpoint}files/{id}/up_success"

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT special case for file: populate url after getting entity id."""
        item = await session.scalar(stmt)

        item.upload_form = str(self.s3.create_presigned_post(
            object_name=f"{item.filename}.{item.extension}",
            callback=self.callback(item.id)
        ))

        return item

    # async def _insert_many(self, stmts: Sequence[Insert])

    @DatabaseManager.in_session
    async def _insert_many(self, stmt: Insert, session: AsyncSession) -> Sequence[Base]:
        """INSERT many objects into the DB database, check token write permission before commit."""
        items = (await session.scalars(stmt)).all()

        for item in items:
            item.upload_form = str(self.s3.create_presigned_post(
                object_name=f"{item.filename}.{item.extension}",
                callback=self.callback(item.id)
            ))

        return items

    @DatabaseManager.in_session
    async def upload_success(self, pk_val, session: AsyncSession):
        file = await self.read(pk_val, fields=['ready', 'upload_form'], session=session)
        setattr(file, 'ready', True)
        setattr(file, 'upload_form', "")

    @DatabaseManager.in_session
    async def download(self, pk_val: List[Any], user_info: UserInfo | None, session: AsyncSession):
        await self._check_permissions("download", user_info, {k: v for k, v in zip(self.pk, pk_val)}, session=session)
        # TODO: test this ^
        file = await self.read(pk_val, fields=['filename', 'extension', 'dl_count'], session=session)

        assert isinstance(file, S3File) # mypy.

        url = self.s3.create_presigned_download_url(f"{file.filename}.{file.extension}")
        file.dl_count += 1
        return url
