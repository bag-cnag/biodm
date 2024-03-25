import requests
from pathlib import Path

from boto3 import client 
from botocore.exceptions import ClientError

# from core.components import UnaryEntityService
from .dbservice import UnaryEntityService
from instance import config

class S3Service(UnaryEntityService):
    """Class that manages AWS S3 bucket transactions. 
    Relevant to associate with files entities which in principle should be unary (i.e. no nested fields)."""

    def __init__(self, app, *args, **kwargs) -> None:
        self.s3_client = client('s3')
        super().__init__(app, *args, **kwargs)

    # Official documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
    def create_presigned_post(self,
                              object_name,
                              fields=[],
                              conditions=[],
                              expiration=config.S3_URL_EXPIRATION):
        conditions.append({"success_action_redirect": 
                           Path(config.SERVER_HOST, "success_file_upload")})
        try:
            return self.s3_client(
                config.S3_BUCKET_NAME,
                object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration
            )
        except ClientError as e:
            self.app.logger.error(e)
            return None

    ## How to use
    # # Generate a presigned S3 POST URL
    # object_name = 'OBJECT_NAME'
    # response = create_presigned_post('BUCKET_NAME', object_name)
    # if response is None:
    #     exit(1)
    # # Demonstrate how another Python program can use the presigned URL to upload a file
    # with open(object_name, 'rb') as f:
    #     files = {'file': (object_name, f)}
    #     http_response = requests.post(response['url'], data=response['fields'], files=files)
    # # If successful, returns HTTP status code 204
    # logging.info(f'File upload HTTP status code: {http_response.status_code}')

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

    # async def create(self, data, stmt_only: bool=False) -> Base | CompositeInsert:
    #     """CREATE, accounting for nested entitites."""
    #     stmts = []
    #     delayed = {}

    #     # For all table relationships, check whether data contains that item.
    #     for key, rel in self.relationships.items():
    #         sub = data.get(key)
    #         if not sub: continue

    #         # Retrieve associated service.
    #         svc = get_class_by_table(Base, rel.target).svc

    #         # Get statement(s) for nested entity:
    #         nested_stmt = await svc.create(sub, stmt_only=True)

    #         # Single nested entity.
    #         if isinstance(sub, dict):
    #             stmts += [nested_stmt]
    #         # List of entities: one - to - many relationship.
    #         elif isinstance(sub, list):
    #             delayed[key] = nested_stmt
    #         else:
    #             raise ValueError("Expecting nested entities to be either passed as dict or list.")
    #         # Remove from data dict to avoid errors on building item statement.
    #         del data[key]

    #     # Statement for original item.
    #     stmt = insert(self.table).values(**data).returning(self.table)

    #     # Pack & return.
    #     composite = self.CompositeInsert(item=stmt, nested=stmts, delayed=delayed)
    #     return composite if stmt_only else await self._insert_composite(composite)

    async def update(self, **kwargs):
        """UPDATE one row."""
        raise NotImplementedError

    async def create_update(self, **kwargs):
        """CREATE UPDATE."""
        raise NotImplementedError

    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError



