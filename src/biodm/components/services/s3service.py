from asyncio import iscoroutine
from math import ceil
from pathlib import Path
from typing import List, Any, Sequence, Dict

from sqlalchemy import Insert, Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from biodm.components.table import Base, S3File
from biodm.exceptions import FileNotUploadedError, FileTooLargeError, ReleaseVersionError
from biodm.managers import DatabaseManager, S3Manager
from biodm.tables import Upload, UploadPart
from biodm.utils.utils import utcnow, classproperty
from biodm.utils.security import UserInfo
from .dbservice import CompositeEntityService


CHUNK_SIZE = 100*1024**2 # 100MB as recomended by AWS S3 documentation.


class S3Service(CompositeEntityService):
    """Class for automatic management of S3 bucket transactions for file resources."""
    post_upload_callback: Path # set by S3Controller.

    @classproperty
    def s3(cls) -> S3Manager:
        return cls.app.s3

    @property
    def key_fields(self) -> List[str]:
        """List of fields used to compute the key."""
        return ['filename', 'extension'] + (['version'] if self.table.is_versioned else [])

    async def gen_key(self, item: S3File, session: AsyncSession) -> str:
        """Generate a unique bucket key from file elements.

        :param item: file
        :type item: S3File
        :param session: current sqla session
        :type session: AsyncSession
        :return: unique s3 bucket file key
        :rtype: str
        """
        key = await getattr(item.awaitable_attrs, 'key')
        assert iscoroutine(key)

        # Populate session in item before that operation.
        item.__dict__['session'] = session
        key = await item.key
        return key

    async def gen_upload_form(self, file: S3File, session: AsyncSession):
        """Populates an Upload for a newly created file. Handling simple post and multipart_upload
        cases.

        :param file: New file
        :type file: S3File
        :param session: current session
        :type session: AsyncSession
        """
        assert isinstance(file, S3File) # mypy.

        if file.size > self.s3.file_size_limit * 1024 ** 3:
            raise FileTooLargeError(f"File exceeding {self.s3.file_size_limit} GB")

        file.upload = Upload()
        session.add(file.upload)
        await session.flush()
        parts = await getattr(file.upload.awaitable_attrs, 'parts')

        key = await self.gen_key(file, session=session)
        n_chunks = ceil(file.size / CHUNK_SIZE)

        mpu = self.s3.create_multipart_upload(key)
        file.upload.s3_uploadId = mpu['UploadId']
        for i in range(1, n_chunks+1):
            parts.append(
                UploadPart(
                    upload_id=file.upload.id,
                    part_number=i,
                    form=str(
                        self.s3.create_upload_part(
                            object_name=key, upload_id=mpu['UploadId'], part_number=i
                        )
                    )
                )
            )

    @DatabaseManager.in_session
    async def _insert(
        self,
        stmt: Insert,
        user_info: UserInfo | None,
        session: AsyncSession
    ) -> (Any | None):
        """INSERT special case for file: populate url after getting entity id."""
        file = await super()._insert(stmt, user_info=user_info, session=session)
        await self.gen_upload_form(file, session=session)
        return file

    @DatabaseManager.in_session
    async def _insert_list(
        self,
        stmts: Sequence[Insert],
        user_info: UserInfo | None,
        session: AsyncSession
    ) -> Sequence[Base]:
        """INSERT many objects into the DB database, check token write permission before commit."""
        files = await super()._insert_list(stmts, user_info=user_info, session=session)
        for file in files:
            await self.gen_upload_form(file, session=session)
        return files

    async def _check_partial_upload(self, file: S3File, session: AsyncSession):
        """Query the bucket to check what parts have been uploaded. Populates etags."""
        if not await getattr(file.awaitable_attrs, 'ready'):
            completed_parts = self.s3.list_multipart_parts(
                await self.gen_key(file, session=session),
                file.upload.s3_uploadId
            )
            for completed in completed_parts['Parts']:
                for upart in file.upload.parts:
                    if upart.part_number == completed['PartNumber']:
                        upart.etag = completed['ETag'].strip('"')

    @DatabaseManager.in_session
    async def _select(self, stmt: Select, session: AsyncSession) -> Base:
        file: S3File = await super()._select(stmt, session=session)
        await self._check_partial_upload(file, session=session)
        return file

    @DatabaseManager.in_session
    async def _select_many(self, stmt: Select, session: AsyncSession) -> Base:
        files: S3File = await super()._select_many(stmt, session=session)
        for file in files:
            await self._check_partial_upload(file, session=session)
        return files

    @DatabaseManager.in_session
    async def complete_multipart(
        self,
        pk_val: List[Any],
        parts: List[Dict[str, Any]],
        session: AsyncSession
    ):
        # parts should take the form of [{'PartNumber': part_number, 'ETag': etag}, ...]
        # Optim: Read that calls super()._select instead of our custom select
        stmt = select(self.table)
        stmt = stmt.where(self.gen_cond(pk_val))
        stmt = self._restrict_select_on_fields(stmt, ['ready', 'upload'] + self.key_fields, None)
        file = await super()._select(stmt, session=session)

        upload = await getattr(file.awaitable_attrs, 'upload')
        upload_id = await getattr(upload.awaitable_attrs, 's3_uploadId')

        complete = self.s3.complete_multipart_upload(
            object_name=await self.gen_key(file, session=session),
            upload_id=upload_id,
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
    async def download(
        self, pk_val: List[Any], user_info: UserInfo | None, session: AsyncSession
    ) -> str:
        """Get File entry from DB, and return a direct download url.

        :param pk_val: key
        :type pk_val: List[Any]
        :param user_info: requesting user info
        :type user_info: UserInfo | None
        :param session: current db session
        :type session: AsyncSession
        :raises FileNotUploadedError: File entry exists but has not been validated yet
        :return: direct download url.
        :rtype: str
        """
        # File management.
        fields = ['dl_count', 'ready'] + self.key_fields
        # Also fetch foreign keys, as some may be necessary for permission check.
        fields += list(c.name for c in self.table.__table__.columns if c.foreign_keys)
        file = await self.read(pk_val, fields=fields, session=session)

        assert isinstance(file, S3File) # mypy.

        await self._check_permissions("download", user_info, file.__dict__, session=session)
        if not file.ready:
            raise FileNotUploadedError("File exists but has not been uploaded yet.")

        url = self.s3.create_presigned_download_url(
            await self.gen_key(file, session=session)
        )
        file.dl_count += 1
        return url

    @DatabaseManager.in_session
    async def release(
        self,
        pk_val: List[Any],
        update: Dict[str, Any],
        session: AsyncSession,
        user_info: UserInfo | None = None,
    ) -> Base:
        if 'size' not in update:
            raise ReleaseVersionError("A new filesize should be provided when releasing a file.")

        # Bumps version.
        file = await super().release(
            pk_val=pk_val,
            update=update,
            session=session,
            user_info=user_info
        )
        # Reset special fields.
        file.created_at = utcnow()
        file.validated_at = None
        file.ready = False
        file.dl_count = 0
        # Generate a new form.
        await self.gen_upload_form(file, session=session)
        return file
