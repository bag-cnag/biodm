
from starlette.routing import Mount, Route

from biodm.components.controllers import Controller, HttpMethod
from biodm.tables import K8sInstance


class K8sController(Controller):
    """
    Bundles Routes located at the root of the app i.e. '/'
    """
    def routes(self, **_) -> Mount:
        return Mount(self.prefix, routes=[
            # Route( '/',             self.method,         methods=[HttpMethod.POST.value]),
        ])
