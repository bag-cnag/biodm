import json
from copy import deepcopy

from starlette.routing import Mount, Route
from starlette.responses import Response

from biodm.components.controllers import Controller, HttpMethod
from biodm.exceptions import ManifestError
from biodm.tables import K8sInstance
from biodm.utils.utils import json_response


class K8sController(Controller):
    """
    """
    @property
    def prefix(self):
        return "/k8s_instances"

    def routes(self, **_) -> Mount:
        return Mount(self.prefix, routes=[
            Route( "/",               self.list_instances, methods=[HttpMethod.GET.value]),
            Route( "/{manifest}",     self.create,         methods=[HttpMethod.POST.value]),
            Route( "/instance/{id}",  self.instance_info,  methods=[HttpMethod.GET.value]),
            Route( "/schema",         self.openapi_schema),
        ])

    @property
    def k8s(self):
        return self.app.k8s

    async def list_instances(self, request) -> Response:
        """
        """
        return '{}'

    async def create(self, request) -> Response:
        """
        ---
        description: Deploys manifest matching identifier and tie it to the user
        parameters:
          - in: path
            id: manifest id
                e.g. /k8s_instances/busybox
          - in: header
            X-User-Token: user token
        """
        manifest = request.path_params.get('manifest')
        if manifest in self.k8s.manifests.__dict__:
            return self.svc.create(self.k8s.manifests.__dict__[manifest])
        raise ManifestError

    async def instance_info(self, request) -> Response:
        """
        """
        return '{}'

    async def openapi_schema(self, _):
        """
        """
        # TODO: move this to route, with an arg like 'view'
        routes = self.routes().routes
        r_create: Route = routes[1]
        mans = self.k8s.manifests
        keys = [k for k in mans.__dict__.keys() if not k.startswith('__')]
        for key in keys:
            r_view = deepcopy(r_create)
            r_view.path = f"/create/{key}"
            def dummy():
                """"""
            dummy.__doc__ = mans.__dict__[key].__doc__
            r_view.endpoint = dummy
            routes.append(r_view)

        return json_response(
            json.dumps(
                self.schema_gen.get_schema(routes=routes),
                indent=self.app.config.INDENT,
            ),
            status_code=200,
        )
