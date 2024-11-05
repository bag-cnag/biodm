import json
from pathlib import Path
from typing import List, Type

from marshmallow import Schema, RAISE
from starlette.routing import Mount, BaseRoute
from starlette.requests import Request
from starlette.responses import RedirectResponse

from biodm.components import S3File
from biodm.components.services import S3Service
from biodm.components.table import Base
from biodm.schemas import PartsEtagSchema
from biodm.exceptions import ImplementionError
from biodm.utils.security import UserInfo
from biodm.utils.utils import json_response
from biodm.routing import PublicRoute, Route
from .controller import HttpMethod
from .resourcecontroller import ResourceController


class S3Controller(ResourceController):
    """Controller for entities involving file management leveraging an S3Service."""
    svc: S3Service

    def __init__(
        self,
        app,
        entity: str = "",
        table: type[Base] | None = None,
        schema: type[Schema] | None = None
    ) -> None:
        # if not hasattr(app, 's3'):
        #     raise ImplementionError("S3 features demanded, but no configuration has been given.")

        # An extra schema to validate complete_multipart input.
        self.parts_etag_schema = PartsEtagSchema(many=True, partial=False, unknown=RAISE)
        super().__init__(app, entity, table, schema)

    def _infer_svc(self) -> Type[S3Service]:
        if not issubclass(self.table, S3File):
            raise ImplementionError(
                "S3Controller should be attached on a table inheriting"
                " from biodm.component.S3File"
            )
        return S3Service

    def routes(self, **_) -> List[Mount | Route] | List[Mount] | List[BaseRoute]:
        """Add an endpoint for successful file uploads and direct download."""
        # flake8: noqa: E501  pylint: disable=line-too-long
        prefix = f'{self.prefix}/{self.qp_id}/'
        file_routes = [
            Route(f'{prefix}download',           self.download,           methods=[HttpMethod.GET]),
            Route(f'{prefix}complete_multipart', self.complete_multipart, methods=[HttpMethod.PUT]),
            PublicRoute(f'{prefix}post_success', self.post_success,       methods=[HttpMethod.GET]),
        ]
        self.svc.post_upload_callback = Path(file_routes[-1].path)

        return file_routes + super().routes()

    async def download(self, request: Request):
        """Returns boto3 presigned download URL with a redirect header.

        ---

        description: Returns a download presigned URL to retrieve file from s3 bucket.
        parameters:
          - in: path
            name: id
        responses:
            307:
                description: Download URL, with a redirect header.
        """
        return RedirectResponse(
            await self.svc.download(
                pk_val=self._extract_pk_val(request),
                user_info=await UserInfo(request),
            )
        )

    async def post_success(self, request: Request):
        """ Used as a callback in the s3 presigned upload urls that are emitted.
            Uppon receival, update entity status in the DB.

        ---

        description: File upload callback - hit by s3 bucket on success upload.
        parameters:
          - in: path
            name: id
        responses:
            201:
                description: Upload confirmation 'Uploaded.'
        """
        await self.svc.post_success(
            pk_val=self._extract_pk_val(request),
            bucket=request.query_params.get('bucket', ''),
            key=request.query_params.get('key', ''),
            etag=request.query_params.get('etag', '').strip('"'),
        )

        return json_response("Uploaded.", status_code=201)

    async def complete_multipart(self, request: Request):
        """Unlike with a pre-signed POST, it is not possible to setup a callback for each part.
        Client has to gather etags for each parts while uploading and sumbit them on this route
        in order to complete a multipart upload.

        :param request: incomming request
        :type request: Request
        :return: Completion notice.
        :rtype: Response

        ---

        description: Multipart upload completion.
        parameters:
          - in: path
            name: id
        responses:
            201:
                description: Completion confirmation 'Completed.'
        """
        await self.svc.complete_multipart(
            pk_val=self._extract_pk_val(request),
            parts=self.parts_etag_schema.loads(await request.body())
        )

        return json_response("Completed.", status_code=201)
