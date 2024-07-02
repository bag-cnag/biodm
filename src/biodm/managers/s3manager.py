from __future__ import annotations
from typing import TYPE_CHECKING

from boto3 import client
from botocore.config import Config
from botocore.exceptions import ClientError

from biodm.component import ApiComponent
from biodm.utils.utils import utcnow

if TYPE_CHECKING:
    from biodm.api import Api


class S3Manager(ApiComponent):
    """Manages requests with an S3 storage instance."""
    def __init__(
        self,
        app: Api,
        endpoint_url,
        bucket_name,
        access_key_id,
        secret_access_key,
        url_expiration,
        pending_expiration,
        region_name,
        file_size_limit
    ) -> None:
        super().__init__(app=app)
        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.url_expiration = url_expiration
        self.pending_expiration = pending_expiration
        self.region_name = region_name
        self.file_size_limit = file_size_limit
        self.s3_client = client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=self.region_name,
            config=Config(
                signature_version='s3'
            ),
        )
        # Will raise an error if configuration doesn't point to a valid bucket.
        # self.s3_client.head_bucket(Bucket=self.bucket_name)

    def create_presigned_post(self,
                              object_name,
                              callback,
    ):
        """ Generates a presigned url + form fiels to upload a given file on s3 bucket.

        Relevant links:
        - https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
        - https://github.com/minio/minio/issues/19811#issue-2317920163
        """
        t = utcnow()
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = '/'.join([t.strftime('%Y%m%d'), self.region_name, 's3', 'aws4_request'])

        conditions = [
            # {"acl": "authenticated-read"},
            {"x-amz-algorithm": algorithm},
            {"x-amz-credential": credential_scope},
            {"x-amz-date": t.isoformat()},
            {"success_action_status": "201"},
            ["starts-with", "$success_action_redirect", ""], # self.app.server_endpoint
            ["content-length-range", 2, self.file_size_limit * 1024 ** 3],
            {"bucket": self.bucket_name},
        ]

        fields = {
            "x-amz-algorithm": algorithm,
            "x-amz-credential": credential_scope,
            'success_action_redirect': callback,
            "x-amz-date": t.isoformat(),
            "success_action_status": "201",
        }

        try:
            return self.s3_client.generate_presigned_post(
                Key=object_name,
                Bucket=self.bucket_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=self.url_expiration
            )
        except ClientError as e:
            # TODO: better error
            raise e

    def create_presigned_download_url(self, object_name):
        """Generate a presigned URL to share an S3 object

        :param object_name: string
        :return: Presigned URL as string.
        """
        try:
            # TODO: see if a callback is possible.
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_name,
                },
                ExpiresIn=self.url_expiration
            )
        except ClientError as e:
            # TODO: better error
            raise e
