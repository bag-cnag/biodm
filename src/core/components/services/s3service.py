import requests
from pathlib import Path

from boto3 import client 
from botocore.exceptions import ClientError

from .dbservice import UnaryEntityService
from instance import config

class S3Service(UnaryEntityService):
    """Class that manages AWS S3 bucket transactions. 
    Automatically associated with files entities which in principle should be unary (i.e. no nested fields)."""
    @property
    def s3(self):
        return self.app.s3
    
    async def create(self, data, stmt_only=False):
        """CREATE accounting for generation of presigned url for 2step file upload."""
        name = data.get("name")
        url = self.create_presigned_post(name)
        if not url:
            raise Exception("Could not generate presigned url.")
        data["url"] = url
        return super().create(data, stmt_only)

    async def read(self, **kwargs):
        """READ one row."""
        raise NotImplementedError

    async def update(self, **kwargs):
        """UPDATE one row."""
        raise NotImplementedError

    async def create_update(self, **kwargs):
        """CREATE UPDATE."""
        raise NotImplementedError

    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError



