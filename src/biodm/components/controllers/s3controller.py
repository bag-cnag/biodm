from typing import List, Type

from marshmallow import Schema, RAISE, ValidationError
import starlette.routing as sr
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from biodm.components import S3File
from biodm.components.services import S3Service
from biodm.components.table import Base
from biodm.schemas import PartsEtagSchema
from biodm.exceptions import DataError, ImplementionError
from biodm.utils.security import UserInfo
from biodm.utils.utils import json_response
from biodm.routing import Route
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

    def routes(self, **_) -> List[sr.Mount | sr.Route] |  List[sr.Mount] | List[sr.Route]:
        """Add an endpoint for successful file uploads and direct download."""
        prefix = f'{self.prefix}/{self.qp_id}/'
        file_routes = [
            Route(f'{prefix}download',        self.download,           methods=[HttpMethod.GET]),
            Route(f'{prefix}complete',        self.complete_multipart, methods=[HttpMethod.PUT]),
        ]
        return file_routes + super().routes()

    async def download(self, request: Request) -> Response:
        """Returns boto3 presigned download URL with a redirect header.

        ---

        description: Returns a download presigned URL to retrieve file from s3 bucket.
        parameters:
          - in: path
            name: id
        responses:
            200:
                description: File download url
                content:
                    application/json:
                        schema:
                            type: string
            404:
                description: Not found.
            409:
                description: Download a file which has not been uploaded.
            500:
                description: S3 Bucket issue.
        """
        return PlainTextResponse(
            await self.svc.download(
                pk_val=self._extract_pk_val(request),
                user_info=await UserInfo(request),
            )
        )

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
        requestBody:
            description: payload.
            required: true
            content:
                application/json:
                    schema:
                        type: array
                        items: PartsEtagSchema
        parameters:
          - in: path
            name: id
        responses:
            201:
                description: Completion confirmation 'Completed.'
            400:
                description: Wrongly formatted completion notice.
            4O4:
                description: Not found.
            500:
                description: S3 Bucket issue.
        """
        flag = True
        try:
            parts = self.parts_etag_schema.loads(await request.body())
            await self.svc.complete_multipart(
                pk_val=self._extract_pk_val(request),
                parts=parts,
            )
            return json_response("Completed.", status_code=201)
        except ValidationError as ve:
            raise DataError(str(ve.messages))
