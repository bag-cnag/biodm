import json
from copy import deepcopy
from typing import List, Type

from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from biodm.components.controllers import Controller, HttpMethod# ResourceController
from biodm.exceptions import ManifestError
from biodm.components import K8sManifest
from biodm.utils.utils import json_response


class K8sController(Controller):
    """Kubernetes Instances Controller.
    Serves unified administration entrypoints to manage all K8sManifest subinstances.
    """
    manifests: List[K8sManifest]
    def __init__(self, app, manifests: List[Type[K8sManifest]]) -> None:
        self.manifests = []
        for manifest in manifests:
            self.manifests.append(manifest(app=app))
        super().__init__(app=app)

    @property
    def prefix(self):
        return "/k8s"

    @property
    def k8s(self):
        return self.app.k8s

    def routes(self, schema: bool=False):
        """Routes for k8s instances management

        :param schema: when called from schema generation, defaults to False
        :type schema: bool
        :rtype: starlette.routing.Mount
        """
        m = Mount(self.prefix, routes=[
            Route("/",               self.list_instances, methods=[HttpMethod.GET]),
            Route("/instance/{id}",  self.instance_info,  methods=[HttpMethod.GET]),
            Route("/schema",         self.openapi_schema, methods=[HttpMethod.GET])
        ])
        if not schema:
            return [m]
        return [m] # TODO
    #     m = Mount(self.prefix, routes=[
    #         Route("/{manifest}",     self.create,         methods=[HttpMethod.POST]),
    #         Route("/",               self.list_instances, methods=[HttpMethod.GET]),
    #         Route("/instance/{id}",  self.instance_info,  methods=[HttpMethod.GET]),
    #         
    #     ])

    #     # Mock up an individual route for each available manifest, copying doc.
    #     r_create = m.routes[0]
    #     assert isinstance(r_create, Route) # mypy

    #     mans = self.k8s.manifests
    #     keys = [k for k in mans.__dict__.keys() if not k.startswith('__')]

    #     for key in keys:
    #         r_view = deepcopy(r_create)
    #         r_view.path = f"/{key}"

    #         def dummy():
    #             """"""
    #         dummy.__doc__ = mans.__dict__[key].__doc__
    #         r_view.endpoint = dummy
    #         m.routes.append(r_view)
    #     return m.routes

    async def list_instances(self, request: Request) -> Response:
        """List all running K8s Instances.
        COMING UP
        """
        return PlainTextResponse('{}')

    async def instance_info(self, request: Request) -> Response:
        """Return info for one running instance.
        COMING UP
        ---
        """
        return PlainTextResponse('{}')
