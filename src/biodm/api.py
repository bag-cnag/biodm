"""BioDM Server Class."""
from asyncio import wait_for
from datetime import datetime
from inspect import getfullargspec
import logging
from time import sleep
from typing import Callable, List, Literal, Optional, Dict, Any, Type

from apispec import APISpec
from starlette_apispec import APISpecSchemaGenerator
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.types import ASGIApp
from sqlalchemy.exc import IntegrityError

from biodm import Scope, config
from biodm.basics import CORE_CONTROLLERS, K8sController
from biodm.components.table import add_versioned_table_methods
from biodm.components.k8smanifest import K8sManifest
from biodm.managers import DatabaseManager, KeycloakManager, S3Manager, K8sManager
from biodm.components.controllers import Controller
from biodm.components.services import UnaryEntityService, CompositeEntityService
from biodm.error import onerror
from biodm.utils.security import AuthenticationMiddleware, PermissionLookupTables
from biodm.utils.utils import to_it
from biodm.utils.apispec import BDMarshmallowPlugin
from biodm.tables import History, ListGroup, Upload, UploadPart
from biodm import __version__ as CORE_VERSION


# pylint: disable=too-few-public-methods
class TimeoutMiddleware(BaseHTTPMiddleware):
    """Emit timeout signals."""
    def __init__(self, app: ASGIApp, timeout: int = 30) -> None:
        self.timeout = timeout
        super().__init__(app, self.dispatch)

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        try:
            return await wait_for(call_next(request), timeout=self.timeout)
        except TimeoutError:
            return HTMLResponse("Request reached timeout.", status_code=504)

# pylint: disable=too-few-public-methods
class HistoryMiddleware(BaseHTTPMiddleware):
    """Log incomming requests into History table AND stdout."""
    def __init__(self, app: ASGIApp, server_host: str) -> None:
        self.server_host = server_host
        super().__init__(app, self.dispatch)

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        endpoint = str(request.url).rsplit(self.server_host, maxsplit=1)[-1]
        body = await request.body()
        entry = {
            'user_username': request.user.display_name,
            'endpoint': endpoint,
            'method': request.method,
            'content': str(body) if body else ""
        }
        try:
            await History.svc.write(entry)
        except IntegrityError as _:
            # Collision may happen in case two anonymous requests hit at the exact same tick.
            try: # Try once more.
                sleep(0.1)
                await History.svc.write(entry)
            except Exception as _:
                # Keep going in any case. History feature should not be blocking.
                pass

        # Log
        timestamp = datetime.now().strftime("%I:%M%p on %B %d, %Y")
        History.svc.app.logger.info(
            f'{timestamp}\t{request.user.display_name}\t{",".join(request.user.groups)}\t'
            f'{endpoint}\t-\t{request.method}'
        )

        return await call_next(request)


class Api(Starlette):
    """ Main Server class.

    - Sets up and holds managers + OpenAPI schema generator
    - Instanciates CORE_CONTROLLERS and passed controllers
      - Sets up routes
    - adds our middlewares
    - listens on events
    """
    logger = logging.getLogger(__name__)
    # Managers
    db: DatabaseManager
    s3: S3Manager
    kc: KeycloakManager
    k8: K8sManager
    # Controllers
    controllers: List[Controller] = []

    def __init__(
        self,
        controllers: Optional[List[Type[Controller]]],
        *args,
        scheme: Literal['http'] | Literal['https'] = 'http',
        manifests: Optional[List[Type[K8sManifest]]] = None,
        debug: bool=False,
        test: bool=False,
        **kwargs,
    ) -> None:
        """instanciate server

        :param controllers: Controller classes
        :type controllers: Optional[List[Type[Controller]]]
        :param scheme: Server scheme, defaults to 'http'
        :type scheme: Literal[&#39;http&#39;] | Literal[&#39;https&#39;], optional
        :param manifests: K8sManifest classes, defaults to None
        :type manifests: Optional[List[Type[K8sManifest]]], optional
        :param debug: Debug mode, **caution:** will reset DB, defaults to False
        :type debug: bool, optional
        :param test: Test mode, defaults to False
        :type test: bool, optional
        """
        # Scheme
        self.scheme = scheme

        # Set runtime flag.
        self.scope = Scope.PROD
        self.scope |= Scope.DEBUG if debug else self.scope
        self.scope |= Scope.TEST if test else self.scope

        # Declare trusted ips.
        self._network_ips = [self.server_endpoint]

        # Logger.
        logging.basicConfig(
            level=logging.DEBUG if Scope.DEBUG in self.scope else logging.INFO,
            format=(
                "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d - %(message)s"
            )
        )
        logging.info("Intializing server.")

        # Managers
        self.deploy_managers()

        # Controllers.
        routes: List[Route] = []
        for ctrl in CORE_CONTROLLERS + (controllers or []):
            routes.extend(self.adopt_controller(ctrl))
        if hasattr(self, 'k8') and manifests:
            routes.extend(self.adopt_controller(K8sController, manifests=manifests))

        # Schema Generator.
        security_scheme = "Authorization"
        self.apispec = APISpecSchemaGenerator(
            APISpec(
                title=config.API_NAME,
                version=config.API_VERSION,
                openapi_version="3.0.2",
                plugins=[BDMarshmallowPlugin()],
                info={
                    "description": config.API_DESCRIPTION,
                    "backend": "BioDM",
                    "backend_version": CORE_VERSION
                },
                security=[{security_scheme: []}]
            )
        )
        self.apispec.spec.components.security_scheme(security_scheme, {
            "type": "http",
            "name": security_scheme.lower(),
            "in": "header",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        })

        # Final setup.
        self._declare_headless_services()

        super().__init__(debug=debug, routes=routes, *args, **kwargs)

        # Middlewares -> Stack goes in reverse order.
        self.add_middleware(HistoryMiddleware, server_host=config.SERVER_HOST)
        self.add_middleware(AuthenticationMiddleware)
        if Scope.DEBUG not in self.scope:
            self.add_middleware(TimeoutMiddleware, timeout=config.SERVER_TIMEOUT)
        # CORS last (i.e. first).
        self.add_middleware(
            CORSMiddleware, allow_credentials=True,
            allow_origins=["*"], # self._network_ips + ["http://localhost:9080"], # + swagger-ui.
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Total-Count"],
            max_age=config.CACHE_MAX_AGE
        )

        # Event handlers
        self.add_event_handler("startup", self.onstart)
        # self.add_event_handler("shutdown", self.on_app_stop)

        # Error handlers
        self.add_exception_handler(RuntimeError, onerror)
        # self.add_exception_handler(DatabaseError, on_error)

    @property
    def server_endpoint(self) -> str:
        """Server address, useful to compute callbacks."""
        return f"{self.scheme}://{config.SERVER_HOST}:{config.SERVER_PORT}/"

    def _parse_config(self, prefix: str) -> Dict[str, Any]:
        """Returns config elements starting by prefix.
        :param prefix: prefix
        :type prefix: str
        :return: config subset as a dict
        :rtype: Dict[str, Any]
        """
        return {
            k.lower().split(f"{prefix}_")[-1]: v
            for k, v in config.__dict__.items()
            if k.lower().startswith(f"{prefix}_")
        }

    def deploy_managers(self) -> None:
        """Conditionally deploy managers. Each manager connects to an external service.
        Appart from the DB, managers are optional, with respect to config population.
        """
        self.db = DatabaseManager(app=self)
        self._network_ips.append(self.db.endpoint)

        for mclass, mprefix in zip(
            (KeycloakManager, S3Manager, K8sManager),
            ('kc', 's3', 'k8')
        ):
            margs = set(getfullargspec(mclass).args) - set(('self', 'app'))
            conf = self._parse_config(mprefix)
            if all(
                (
                    param in conf and (conf[param] is not None)
                    for param in margs
                )
            ):
                setattr(self, mprefix, mclass(app=self, **conf))
                self._network_ips.append(getattr(self, mprefix).endpoint)
                self.logger.info("%s Manager - UP.", mprefix.upper())
            else:
                self.logger.info("%s Manager - SKIPPED (no config).", mprefix.upper())

    def adopt_controller(self, controller: Type[Controller], **kwargs) -> List[Route]:
        """Instanciate a controller and return its associated routes."""
        c = controller(app=self, **kwargs)
        # Keep Track of controllers.
        self.controllers.append(c)
        return to_it(c.routes())

    def _declare_headless_services(self) -> None:
        """Headless Services.

        For entities that are managed internally: i.e. not exposing routes.

        Since a controller normally instanciates the service, and it does so
        because the services needs a reference the app instance.
        If more useful cases for this show up we might want to design a cleaner solution.
        """
        History.svc    = UnaryEntityService(app=self, table=History)
        UploadPart.svc = UnaryEntityService(app=self, table=UploadPart)
        ListGroup.svc  = CompositeEntityService(app=self, table=ListGroup)
        Upload.svc     = CompositeEntityService(app=self, table=Upload)

    async def onstart(self) -> None:
        """server start event.
        - Setup permission lookup tables
        - Reinitialize DB in DEBUG mode.
        """
        PermissionLookupTables.setup_permissions(self)
        add_versioned_table_methods()
        if Scope.DEBUG in self.scope:
            await self.db.init_db()
