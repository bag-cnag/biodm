from pathlib import Path
from typing import List, Any, Tuple, Dict, Callable, TypeVar, overload


from boto3 import client
from botocore.exceptions import ClientError
from sqlalchemy import Insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from starlette.responses import RedirectResponse

from biodm.managers import DatabaseManager, S3Manager
from biodm.utils.security import UserInfo
from .dbservice import UnaryEntityService


class S3Service(UnaryEntityService):
    """Class that manages AWS S3 bucket transactions.
    Automatically associated with files entities which in principle should be unary."""
    @property
    def s3(self) -> S3Manager:
        return self.app.s3

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT special case for file: populate url after getting entity id."""
        item = await session.scalar(stmt)

        item.upload_form = str(self.s3.create_presigned_post(
            object_name=f"{item.filename}.{item.extension}",
            callback=f"{self.app.server_endpoint}files/up_success/{item.id}"
        ))

        return item

    @DatabaseManager.in_session
    async def upload_success(self, pk_val, session: AsyncSession):
        file = await session.scalar(
            select(self.table).where(self.gen_cond(pk_val))
        )
        if not file:
            raise RuntimeError("Critical: s3 ref unknonw in DB!")
        file.ready = True

    async def download(self, pk_val: List[Any], user_info: UserInfo = None):
        await self._check_permissions("download", user_info, {k: v for k, v in zip(self.pk, pk_val)})
        # TODO: test this ^
        file = await self.read(pk_val, fields=['filename', 'extension'])
        return RedirectResponse(
            self.s3.create_presigned_download_url(f"{file.filename}.{file.extension}")
        )

    async def download_success(self, pk_val):
        # TODO: add a counter to S3File + implement increment here.
        pass
