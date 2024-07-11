from asyncio import wait_for
from inspect import getfullargspec
import logging
import logging.config
from time import sleep
from typing import Callable, List, Optional, Dict, Any, Type
from types import ModuleType

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from starlette_apispec import APISpecSchemaGenerator
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response, HTMLResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.types import ASGIApp
from sqlalchemy.exc import IntegrityError

from biodm import Scope, config
from biodm.basics import CORE_CONTROLLERS, K8sController
from biodm.component import ApiComponent
from biodm.managers import DatabaseManager, KeycloakManager, S3Manager, K8sManager
from biodm.components.controllers import Controller
from biodm.components.services import UnaryEntityService, CompositeEntityService
from biodm.error import onerror
from biodm.exceptions import RequestError
from biodm.utils.security import UserInfo
from biodm.utils.utils import to_it
from biodm.tables import History, ListGroup
from biodm import __version__ as CORE_VERSION


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


class HistoryMiddleware(BaseHTTPMiddleware):
    """Logins in authenticated user requests in History."""
    def __init__(self, app: ASGIApp, server_host: str) -> None:
        self.server_host = server_host
        super().__init__(app, self.dispatch)

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        user_info = await UserInfo(request)
        username = user_info.info[0] if user_info.info else "anon" # Needs a key.

        body = await request.body()
        entry = {
            'username_user': username,
            'endpoint': str(request.url).rsplit(self.server_host, maxsplit=1)[-1],
            'method': request.method,
            'content': str(body) if body else ""
        }
        try:
            await History.svc.create(entry)
        except IntegrityError as _:
            # Collision may happen in case two anonymous requests hit at the exact same tick.
            try: # Try once more.
                sleep(0.1)
                await History.svc.create(entry)
            except:
                pass
        finally: # Keep going in any case. History feature should not be blocking.
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
        instance: Optional[Dict[str, ModuleType]]=None,
        debug: bool=False,
        test: bool=False,
        *args,
        **kwargs
    ) -> None:
        self.scope = Scope.PROD
        if debug:
            self.scope |= Scope.DEBUG
        if test:
            self.scope |= Scope.TEST

        self._network_ips = [self.server_endpoint]

        ## Instance Info.
        instance = instance or {}

        # TODO: debug
        # m = instance.get('manifests')
        # if m:
        #     config.K8_MANIFESTS = m

        ## Logger.
        logging.basicConfig(
            level=logging.DEBUG if Scope.DEBUG in self.scope else logging.INFO,
            format=(
                "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d - %(message)s"
            )
        )
        logging.info("Intializing server.")

        ## Managers
        self.deploy_managers()

        ## Controllers.
        classes = CORE_CONTROLLERS + (controllers or [])
        classes.append(K8sController)
        routes = self.adopt_controllers(classes)

        ## Schema Generator.
        self.apispec = APISpecSchemaGenerator(
            APISpec(
                title=config.API_NAME,
                version=config.API_VERSION,
                openapi_version="3.0.0",
                plugins=[MarshmallowPlugin()],
                info={"description": "", "backend": "biodm", "backend_version": CORE_VERSION},
            )
        )
        jwt_scheme = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        self.apispec.spec.components.security_scheme("jwt", jwt_scheme)

        """Headless Services

            For entities that are managed internally: not exposing routes.
            i.e. only ListGroups and History atm

            Since the controller normally instanciates the service, and it does so
            because the services needs to access the app instance.
            If more useful cases for this show up we might want to design a cleaner solution.
        """
        History.svc = UnaryEntityService(app=self, table=History)
        ListGroup.svc = CompositeEntityService(app=self, table=ListGroup)

        super().__init__(debug, routes, *args, **kwargs)

        ## Middlewares
        self.add_middleware(HistoryMiddleware, server_host=config.SERVER_HOST)
        self.add_middleware(
            CORSMiddleware, allow_credentials=True,
            allow_origins=self._network_ips + ["http://localhost:9080"], # + swagger-ui.
            allow_methods=["*"],
            allow_headers=["*"],
            max_age=config.CACHE_MAX_AGE
        )
        if self.scope is Scope.PROD:
            self.add_middleware(TimeoutMiddleware, timeout=config.SERVER_TIMEOUT)

        # Event handlers
        self.add_event_handler("startup", self.onstart)
        # self.add_event_handler("shutdown", self.on_app_stop)

        # Error handlers
        self.add_exception_handler(RequestError, onerror)
        # self.add_exception_handler(DatabaseError, on_error)
        # self.add_exception_handler(Exception, on_error)

    @property
    def server_endpoint(self) -> str:
        return f"{config.SERVER_SCHEME}{config.SERVER_HOST}:{config.SERVER_PORT}/"

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
                    param in conf and bool(conf[param])
                    for param in margs
                )
            ):
                setattr(self, mprefix, mclass(app=self, **conf))
                self._network_ips.append(getattr(self, mprefix).endpoint)
                self.logger.info(f"{mprefix.upper()} Manager - UP.")
            else:
                self.logger.info(f"{mprefix.upper()} Manager - SKIPPED (no config).")

    def adopt_controllers(self, controllers: List[Type[Controller]]) -> List[Route]:
        """Adopts controllers, and their associated routes."""
        routes: List[Route] = []
        for controller in controllers:
            # Instanciate.
            c = controller(app=self)
            # Fetch and add routes.
            routes.extend(to_it(c.routes()))
            # Keep Track of controllers.
            self.controllers.append(c)
        return routes

    async def onstart(self) -> None:
        if Scope.DEBUG in self.scope:
            """Dev mode: drop all and create tables."""
            await self.db.init_db()
