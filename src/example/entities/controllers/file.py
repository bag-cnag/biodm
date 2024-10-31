from typing import List

from biodm import config
from biodm.components.controllers import S3Controller, HttpMethod
from biodm.exceptions import UnauthorizedError
from biodm.utils.security import UserInfo
from biodm.routing import Route

from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse #, RedirectResponse
from starlette.routing import BaseRoute, Mount

from entities import tables


class FileController(S3Controller):
    def routes(self, **_) -> List[Mount | Route] | List[Mount] | List[BaseRoute]:
        """Adds a /files/id/visualize route.

        :return: Extended route list.
        :rtype: List[Mount | Route] | List[Mount] | List[BaseRoute]
        """
        return [
            Route(f"{self.prefix}/{self.qp_id}/visualize", self.visualize, methods=[HttpMethod.PUT])
        ] + super().routes(**_)

    async def visualize(self, request: Request) -> Response:
        """

        ---

        description: Starts a visualizer instance for this file.
        parameters:
          - in: path
            name: id
        responses:
            200:
                description: Visualizer instance started, returns visitable url
            400:
                description: Resource exists, but this file has not been uploaded yet.
            404:
                description: Not Found
        """
        vis_svc = tables.Visualization.svc

        vis_data = {'file_id': int(request.path_params.get('id'))}

        if not request.user.is_authenticated:
            raise UnauthorizedError()

        vis_data["user_username"] = request.user.display_name

        vis = await vis_svc.write(data=vis_data, stmt_only=False, user_info=request.user)

        return PlainTextResponse(f"http://{config.K8_HOST}/{vis.name}/")
