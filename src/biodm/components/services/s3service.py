from asyncio import iscoroutine
from math import ceil
from typing import List, Any, Sequence, Dict, Type

from sqlalchemy import Insert
from sqlalchemy.ext.asyncio import AsyncSession


from biodm.components.table import Base, S3File
from biodm.exceptions import FileNotUploadedError
from biodm.managers import DatabaseManager, S3Manager
from biodm.tables import Upload, UploadPart
from biodm.utils.utils import utcnow, classproperty
from biodm.utils.security import UserInfo
from .dbservice import CompositeEntityService


CHUNK_SIZE = 100*1024**2 # 100MB as recomended by AWS S3 documentation.


class S3Service(CompositeEntityService):
    """Class for automatic management of S3 bucket transactions for file resources."""
    @classproperty
    def s3(cls) -> S3Manager:
        return cls.app.s3

    def post_callback(self, item) -> str:
        mapping = { # Map primary key values to route elements.
            key: getattr(item, key)
            for key in self.table.pk
        }

        route = str(self.table.ctrl.post_upload_callback) # TODO: svc argument ?
        for key, val in mapping.items():
            route = route.replace("{" + f"{key}" + "}", str(val))

        srv = self.app.server_endpoint.strip('/')
        return f"{srv}{route}"

    async def gen_key(self, item, session: AsyncSession):
        await session.refresh(item, ['filename', 'extension']) 
        version = ""
        if self.table.is_versioned:
            await session.refresh(item, ['version'])
            version = "_v" + str(item.version)

        key_salt = await getattr(item.awaitable_attrs, 'key_salt')
        if iscoroutine(key_salt):
            item.__dict__['session'] = session
            key_salt = await item.key_salt
        return f"{key_salt}_{item.filename}{version}.{item.extension}"

    async def gen_upload_form(self, file: S3File, session: AsyncSession):
        """Populates an Upload for a newly created file. Handling simple post and multipart_upload
        cases.

        :param file: New file
        :type file: S3File
        :param session: current session
        :type session: AsyncSession
        """
        assert isinstance(file, S3File) # mypy.

        file.upload = Upload()
        session.add(file.upload)
        await session.flush()
        parts = await getattr(file.upload.awaitable_attrs, 'parts')

        key = await self.gen_key(file, session=session)
        n_chunks = ceil(file.size/CHUNK_SIZE)

        if n_chunks > 1:
            res = self.s3.create_multipart_upload(key)
            file.upload.s3_uploadId = res['UploadId']
            for i in range(1, n_chunks+1):
                parts.append(
                    UploadPart(
                        id_upload=file.upload.id,
                        part_number=i,
                        form=str(
                            self.s3.create_upload_part(
                                object_name=key, upload_id=res['UploadId'], part_number=i
                            )
                        )
                    )
                )
        else:
            parts.append(
                UploadPart(
                    id_upload=file.upload.id,
                    form=str(
                        self.s3.create_presigned_post(
                            object_name=key,
                            callback=self.post_callback(file)
                        )
                    )
                )
            )

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT special case for file: populate url after getting entity id."""
        file = await super()._insert(stmt, session=session)
        await self.gen_upload_form(file, session=session)
        return file

    @DatabaseManager.in_session
    async def _insert_list(self, stmts: Sequence[Insert], session: AsyncSession) -> Sequence[Base]:
        """INSERT many objects into the DB database, check token write permission before commit."""
        files = await super()._insert_list(stmts, session=session)
        for file in files:
            await self.gen_upload_form(file, session=session)
        return files

    @DatabaseManager.in_session
    async def post_success(self, pk_val: List[Any], session: AsyncSession):
        file = await self.read(pk_val, fields=['ready', 'upload'], session=session)
        file.validated_at = utcnow()
        file.ready = True
        file.upload_id, file.upload = None, None

    @DatabaseManager.in_session
    async def complete_multipart(
        self,
        pk_val: List[Any],
        parts: List[Dict[str, Any]],
        session: AsyncSession
    ):
        # parts should take the form of [{'PartNumber': part_number, 'ETag': etag}, ...]
        file = await self.read(pk_val, fields=['ready', 'upload'], session=session)
        upload = await getattr(file.awaitable_attrs, 'upload')
        complete = self.s3.complete_multipart_upload(
            object_name=await self.gen_key(file, session=session),
            upload_id=upload.s3_uploadId,
            parts=parts
        )
        if (
            not complete.get('ResponseMetadata', {}).get('HTTPStatusCode', None) or
            complete['ResponseMetadata']['HTTPStatusCode'] != 200
        ):
            # TODO: think about what happens to file/upload. use: abort_multipart_upload ?
            raise FileNotUploadedError("Multipart upload failed: cancelled")

        file.validated_at = utcnow()
        file.ready = True
        file.upload_id, file.upload = None, None

    @DatabaseManager.in_session
    async def download(self, pk_val: List[Any], user_info: UserInfo | None, session: AsyncSession):
        # File management.
        fields = ['filename', 'extension', 'dl_count', 'ready']
        # Also fetch foreign keys, as some may be necessary for permission check.
        fields += list(c.name for c in self.table.__table__.columns if c.foreign_keys)
        file = await self.read(pk_val, fields=fields, session=session)

        assert isinstance(file, S3File) # mypy.

        await self._check_permissions("download", user_info, file.__dict__, session=session)

        if not file.ready:
            raise FileNotUploadedError("File exists but has not been uploaded yet.")

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
        file = await super().release(
            pk_val=pk_val,
            fields=fields,
            update=update,
            session=session,
            user_info=user_info
        )
        file.created_at = utcnow()
        file.validated_at = None
        file.ready = False
        file.dl_count = 0
        await self.gen_upload_form(file, session=session)
        return file
