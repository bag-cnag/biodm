import json
from copy import deepcopy

from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from biodm.components.controllers import ResourceController, HttpMethod
from biodm.exceptions import ManifestError
from biodm.tables import K8sInstance
from biodm.schemas import K8sinstanceSchema
from biodm.utils.utils import json_response


class K8sController(ResourceController):
    """Kubernetes Instances Controller.

    """
    def __init__(self, app) -> None:
        super().__init__(app=app, entity="k8sinstance", table=K8sInstance, schema=K8sinstanceSchema)

    # @property
    # def prefix(self):
    #     return "/k8s_instances"

    def routes(self, schema: bool=False):
        """Routes for k8s instances management

        :param schema: when called from schema generation, defaults to False
        :type schema: bool
        :rtype: starlette.routing.Mount
        """
        m = Mount(self.prefix, routes=[
            Route("/{manifest}",     self.write,         methods=[HttpMethod.POST.value]),
            Route("/",               self.list_instances, methods=[HttpMethod.GET.value]),
            Route("/instance/{id}",  self.instance_info,  methods=[HttpMethod.GET.value]),
            Route("/schema",         self.openapi_schema),
        ])
        if not schema:
            return [m]

        # Mock up an individual route for each available manifest, copying doc.
        r_create = m.routes[0]
        assert isinstance(r_create, Route) # mypy

        mans = self.k8s.manifests
        keys = [k for k in mans.__dict__.keys() if not k.startswith('__')]

        for key in keys:
            r_view = deepcopy(r_create)
            r_view.path = f"/{key}"

            def dummy():
                """"""
            dummy.__doc__ = mans.__dict__[key].__doc__
            r_view.endpoint = dummy
            m.routes.append(r_view)
        return m.routes

    @property
    def k8s(self):
        return self.app.k8s

    async def list_instances(self, request: Request) -> Response:
        """ List running K8s Instances.
        """
        return PlainTextResponse('{}')

    async def write(self, request: Request) -> Response:
        """Deploys K8s Instance.

        ---
        description: Deploy manifest matching identifier and tie it to requesting user.
        parameters:
          - in: path
            name: id
            description: manifest id
        """
        manifest = request.path_params.get('manifest')
        if manifest in self.k8s.manifests.__dict__:
            return self.svc.write(self.k8s.manifests.__dict__[manifest])
        raise ManifestError

    async def instance_info(self, request: Request) -> Response:
        """ Instance info.

        ---
        """
        return PlainTextResponse('{}')
