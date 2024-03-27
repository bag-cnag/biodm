import requests
from pathlib import Path

from boto3 import client 
from botocore.exceptions import ClientError

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
            return self.s3_client.generate_presigned_post(
                config.S3_BUCKET_NAME,
                object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration
            )
        except ClientError as e:
            self.app.logger.error(e)
            return None
    
    def create_presigned_download_url(self, object_name, expiration=config.S3_URL_EXPIRATION):
        """Generate a presigned URL to share an S3 object

        :param bucket_name: string
        :param object_name: string
        :param expiration: Time in seconds for the presigned URL to remain valid
        :return: Presigned URL as string. If error, returns None.
        """
        try:
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': config.S3_BUCKET_NAME, 'Key': object_name},
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

    async def update(self, **kwargs):
        """UPDATE one row."""
        raise NotImplementedError

    async def create_update(self, **kwargs):
        """CREATE UPDATE."""
        raise NotImplementedError

    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError



