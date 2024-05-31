from pathlib import Path
from typing import List, Any, Tuple, Dict, Callable, TypeVar, overload


from boto3 import client
from botocore.exceptions import ClientError
from h11 import Data
from sqlalchemy import Insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from biodm.managers import DatabaseManager
from .dbservice import UnaryEntityService


class S3Service(UnaryEntityService):
    """Class that manages AWS S3 bucket transactions.
    Automatically associated with files entities which in principle should be unary."""
    @property
    def s3(self):
        return self.app.s3

    @DatabaseManager.in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT special case for file: populate url after getting entity id."""
        item = await session.scalar(stmt)

        item.url = str(self.s3.create_presigned_post(
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

    async def download(self, pk_val):
        file = await self.read(pk_val)
        return self.s3.create_presigned_download_url(f"{file.filename}.{file.extension}")

    async def download_success(self, pk_val):
        pass

    # async def read(self, **kwargs):
    #     """READ one row."""
    #     raise NotImplementedError

    # async def update(self, **kwargs):
    #     """UPDATE one row."""
    #     raise NotImplementedError

    # async def create_update(self, **kwargs):
    #     """CREATE UPDATE."""
    #     raise NotImplementedError

    # async def delete(self, **kwargs):
    #     """DELETE."""
    #     raise NotImplementedError
