from pathlib import Path
from typing import List

from starlette.routing import Route, Mount
from starlette.requests import Request

from biodm.components.services import S3Service
from biodm.utils.utils import json_response
from .controller import HttpMethod
from .resourcecontroller import ResourceController


class S3Controller(ResourceController):
    """Controller for entities involving file management leveraging an S3Service."""
    def _infer_svc(self) -> S3Service:
        return S3Service

    def routes(self, child_routes=[], **_) -> List[Mount | Route]:
        """Add an endpoint for successful file uploads and direct download."""
        # TODO: check if AWS calls back with POST or PUT
        file_routes = [
            Route(f'/download/{self.qp_id}',    self.download,              methods=[HttpMethod.GET.value]),
            # Route(f'/up_success/{self.qp_id}',  self.file_upload_success,   methods=[HttpMethod.POST.value]),
            Route(f'/up_success/{self.qp_id}',  self.upload_success,   methods=[HttpMethod.GET.value]),
            Route(f'/dl_success/{self.qp_id}',  self.download_success, methods=[HttpMethod.POST.value]),
        ]
        self.route_upload_callback = Path(self.prefix, file_routes[1].path)
        return super().routes(child_routes=child_routes + file_routes)

    # TODO: Decorate with permissions.
    async def download(self, request: Request):
        """Returns aws s3 direct download URL with a redirect header."""
        return json_response(
            await self.svc.download(
                pk_val=self._extract_pk_val(request)
            ),
            status_code=200
        )

    async def download_success(self, request: Request):
        """Used as a callback in s3 presigned download urls for statistics."""
        # TODO: Implement
        pass

    async def upload_success(self, request: Request):
        """ Used as a callback in the s3 presigned upload urls that are emitted.
            Uppon receival, update entity status in the DB."""
        await self.svc.upload_success(pk_val=self._extract_pk_val(request))
        return json_response("Uploaded.", status_code=201)
