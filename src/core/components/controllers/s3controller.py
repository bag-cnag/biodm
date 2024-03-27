from pathlib import Path

from starlette.routing import Route, Mount

from core.components.services import S3Service
from .controller import ActiveController, HttpMethod


class S3Controller(ActiveController):
    """Controller for entities involving file management leveraging an S3Service."""
    # def __init__(self,
    #              *args,
    #              **kwargs):
    #     super().__init__(*args, **kwargs)
    def _infer_svc(self) -> S3Service:
        return S3Service

    def routes(self, child_routes=[]) -> Mount:
        """Add an endpoint for successful file uploads and direct download."""
        # TODO: check if AWS calls back with POST or PUT
        file_routes = [
            Route(f'/download/{self.qp_id}',    self.download,              methods=[HttpMethod.GET.value]),
            Route(f'/up_success/{self.qp_id}',  self.file_upload_success,   methods=[HttpMethod.POST.value]),
            Route(f'/dl_success/{self.qp_id}',  self.file_download_success, methods=[HttpMethod.POST.value]),
        ]
        self.route_upload_callback = Path(self.prefix,  file_routes[1].path)
        return super().routes(child_routes=child_routes + file_routes)

    # TODO: Decorate with permissions.
    async def download(self, request):
        """Returns aws s3 direct download URL with a redirect header.  
        """
        # TODO: Implement
        pass

    async def file_download_success(self, request):
        """Used as a callback in s3 presigned download urls for statistics."""
        # TODO: Implement
        pass

    async def file_upload_success(self, request):
        """ Used as a callback in the s3 presigned upload urls that are emitted.
            Uppon receival, update entity status in the DB."""

        # 1. read request
            # -> get id
            # -> get path ? 
        # 2. self.svc.file_ready() -> set ready state (and update path ?  
        # TODO: Implement
        pass