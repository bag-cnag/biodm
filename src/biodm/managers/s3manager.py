from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

from boto3 import client
from botocore.exceptions import ClientError
if TYPE_CHECKING:
    from biodm.api import Api

class S3Manager():
    def __init__(self, app: Api):
        self.app = app
        self.s3_client = client('s3')

    # Official documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
    def create_presigned_post(self,
                              object_name,
                              fields=[],
                              conditions=[],
                              expiration=None):
        expiration = expiration if expiration else self.app.config.S3_URL_EXPIRATION
        conditions.append({"success_action_redirect": 
                           Path(self.app.config.SERVER_HOST, "success_file_upload")})
        try:
            return self.s3_client.generate_presigned_post(
                self.app.config.S3_BUCKET_NAME,
                object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration
            )
        except ClientError as e:
            self.app.logger.error(e)
            return None
    
    def create_presigned_download_url(self, object_name, expiration=None):
        """Generate a presigned URL to share an S3 object

        :param bucket_name: string
        :param object_name: string
        :param expiration: Time in seconds for the presigned URL to remain valid
        :return: Presigned URL as string. If error, returns None.
        """
        expiration = expiration if expiration else self.app.config.S3_URL_EXPIRATION
        try:
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.app.config.S3_BUCKET_NAME, 'Key': object_name},
                ExpiresIn=expiration
            )
        except ClientError as e:
            self.app.logger.error(e)
            return None

    ## How to use
    # import requests
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
