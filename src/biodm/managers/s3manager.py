from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

from boto3 import client
from botocore.exceptions import ClientError

from biodm.component import ApiComponent

if TYPE_CHECKING:
    from biodm.api import Api


"""
##How to use
# import requests
## Generate a presigned S3 POST URL
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
"""


class S3Manager(ApiComponent):
    """Manages requests with an S3 storage instance."""
    def __init__(self, app: Api, endpoint_url, bucket_name, url_expiration, pending_expiration):
        super().__init__(app=app)
        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.url_expiration = url_expiration
        self.pending_expiration = pending_expiration
        self.s3_client = client('s3')

    def create_presigned_post(self,
                              object_name,
                              fields=None,
                              condition=None,
                              expiration=None):
        """
        From boto3 official doc:
        - https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
        """
        fields = fields or []
        conditions = conditions or []
        expiration = expiration if expiration else self.url_expiration
        conditions.append({"success_action_redirect": 
                           Path(self.app.config.SERVER_HOST, "success_file_upload")})
        try:
            return self.s3_client.generate_presigned_post(
                self.bucket_name,
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
        expiration = expiration if expiration else self.url_expiration
        try:
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
        except ClientError as e:
            self.app.logger.error(e)
            return None

