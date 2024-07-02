from pathlib import Path
from typing import List, Type

from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import RedirectResponse

from biodm.components import S3File
from biodm.components.services import S3Service
from biodm.exceptions import ImplementionError
from biodm.utils.security import UserInfo
from biodm.utils.utils import json_response
from .controller import HttpMethod
from .resourcecontroller import ResourceController


class S3Controller(ResourceController):
    """Controller for entities involving file management leveraging an S3Service."""
    def _infer_svc(self) -> Type[S3Service]:
        if not issubclass(self.table, S3File):
            raise ImplementionError(
                "S3Controller should be paired or given a table inheriting"
                " from biodm.component.S3File"
            )
        return S3Service

    def routes(self, **_) -> List[Mount | Route]:
        """Add an endpoint for successful file uploads and direct download."""
        file_routes = [
            Route(f'{self.prefix}/download/{self.qp_id}',    self.download,         methods=[HttpMethod.GET.value]),
            Route(f'{self.prefix}/up_success/{self.qp_id}',  self.upload_success,   methods=[HttpMethod.GET.value]),
        ]
        self.route_upload_callback = Path(self.prefix, file_routes[1].path)

        return file_routes + super().routes()

    async def download(self, request: Request):
        """Returns aws s3 direct download URL with a redirect header."""
        assert isinstance(self.svc, S3Service) # mypy.

        return RedirectResponse(
            await self.svc.download(
                pk_val=self._extract_pk_val(request),
                user_info=await UserInfo(request),
            )
        )

    async def upload_success(self, request: Request):
        """ Used as a callback in the s3 presigned upload urls that are emitted.
            Uppon receival, update entity status in the DB."""
        assert isinstance(self.svc, S3Service) # mypy.

        await self.svc.upload_success(pk_val=self._extract_pk_val(request))

        return json_response("Uploaded.", status_code=201)
