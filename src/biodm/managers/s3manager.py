from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, List

from boto3 import client
from botocore.exceptions import ClientError
from starlette.datastructures import Secret

from biodm.exceptions import FileUploadCompleteError, ManagerError
from biodm.component import ApiManager

if TYPE_CHECKING:
    from biodm.api import Api


class S3Manager(ApiManager):
    """Manages requests with an S3 storage instance."""
    def __init__(
        self,
        app: Api,
        endpoint_url: str,
        bucket_name: str,
        access_key_id: Secret,
        secret_access_key: Secret,
        url_expiration: int,
        pending_expiration: int,
        region_name: str,
        file_size_limit: int
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
            aws_access_key_id=str(access_key_id),
            aws_secret_access_key=str(secret_access_key),
            region_name=self.region_name,
        )
        # Will raise an error if configuration doesn't point to a valid bucket.
        # self.s3_client.head_bucket(Bucket=self.bucket_name)

    @property
    def endpoint(self) -> str:
        return self.endpoint_url

    def create_presigned_download_url(self, object_name: str) -> str:
        """Generate a presigned URL to share an S3 object

        :param object_name: Object Key
        :type object_name: String
        :return: Presigned URL as string.
        """
        try:
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_name,
                },
                ExpiresIn=self.url_expiration
            )

        except ClientError as e:
            raise ManagerError(str(e))

    def create_multipart_upload(self, object_name: str) -> Dict[str, str]:
        """Create multipart upload

        - resource: https://vsgump.medium.com/enhancing-file-uploads-to-amazon-s3-with-pre-signed-urls-and-threaded-parallelism-23890b9d6c54

        :param object_name: object key
        :type object_name: str
        :raises FailedCreate: When client fails to create multipart upload
        :return: Multipart upload descriptior, containing 'UploadId'
        :rtype: Dict[str, str]
        """
        try:
            return self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_name,
            )

        except ClientError as e:
            raise ManagerError(str(e))

    def create_upload_part(self, object_name, upload_id, part_number):
        try:
            return self.s3_client.generate_presigned_url(
                    'upload_part',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': object_name,
                        'PartNumber': part_number,
                        'UploadId': upload_id
                    },
                    ExpiresIn=self.url_expiration
                )

        except ClientError as e:
            raise ManagerError(str(e))

    def complete_multipart_upload(
        self,
        object_name: str,
        upload_id: str,
        parts: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """Multipart upload Completion notice

        :param object_name: object key
        :type object_name: str
        :param upload_id: multipart upload id
        :type upload_id: str
        :param parts: Part - ETag mapping for all parts
        :type parts: List[Dict[str, str]]
        :raises FileUploadCompleteError: Bucket returns an error
        :return: Bucket response
        :rtype: Dict[str, str]
        """
        try:
            return self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_name,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )

        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityTooSmall':
                raise FileUploadCompleteError(
                    "Completion notice received for a partially uploaded file - "
                    "bucket responded with 'EntityTooSmall'"
                )
            else:
                raise ManagerError(str(e.response['Error']))

    def list_multipart_parts(self, object_name: str, upload_id: str) -> Dict[str, str]:
        try:
            return self.s3_client.list_parts(
                Bucket=self.bucket_name,
                Key=object_name,
                UploadId=upload_id,
            )

        except ClientError as e:
            raise ManagerError(str(e.response['Error']))

    def abort_multipart_upload(self, object_name: str, upload_id: str) -> Dict[str, str]:
        """Multipart upload termination notice

        :param object_name: object key
        :type object_name: str
        :param upload_id: multipart upload id
        :type upload_id: str
        :raises FailedCreate: Bucket returns an error
        :return: Bucket response
        :rtype: Dict[str, str]
        """
        try:
            return self.s3_client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_name,
                UploadId=upload_id
            )

        except ClientError as e:
            raise ManagerError(str(e))
