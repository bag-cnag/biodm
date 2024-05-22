from asyncio import wait_for
import logging
import logging.config
from typing import List, Optional, Dict, Any
from types import ModuleType

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from starlette.schemas import SchemaGenerator
from starlette.types import ASGIApp
from starlette.config import Config

from biodm import Scope, config
from biodm.basics import CORE_CONTROLLERS, K8sController
from biodm.component import ApiComponent
from biodm.managers import DatabaseManager, KeycloakManager, S3Manager, K8sManager
from biodm.components.controllers import Controller
from biodm.components.services import UnaryEntityService, CompositeEntityService
from biodm.error import onerror
from biodm.exceptions import RequestError
from biodm.utils.utils import to_it
from biodm.utils.security import extract_and_decode_token, auth_header
from biodm.tables import History, ListGroup
from biodm import __version__ as CORE_VERSION


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Emit timeout signals."""
    def __init__(self, app: ASGIApp, timeout: int = 30) -> None:
        self.timeout = timeout
        super().__init__(app, self.dispatch)

    async def dispatch(self, request, call_next):
        try:
            return await wait_for(call_next(request), timeout=self.timeout)
        except TimeoutError:
            return HTMLResponse("Request reached timeout.", status_code=504)


class HistoryMiddleware(BaseHTTPMiddleware):
    """Logins in authenticated user requests in History."""
    def __init__(self, app: ASGIApp, server_host: str) -> None:
        self.server_host = server_host
        super().__init__(app, self.dispatch)

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if auth_header(request):
            app = History.svc.app
            try:
                username, _, _ = await extract_and_decode_token(app.kc, request)
            except Exception as _:
                #  Token decoding failed: the request will fail later.
                # return await call_next(request)
                # return await (call_next(request))
                return response

            body = await request.body()
            entry = {
                'username_user': username,
                'endpoint': str(request.url).rsplit(self.server_host, maxsplit=1)[-1],
                'method': request.method,
                'content': str(body) if body else ""
            }
            await History.svc.create(entry, stmt_only=False)
        return response
        # return (await call_next)(request)


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
    db: DatabaseManager = None
    s3: S3Manager = None
    kc: ApiComponent = None
    k8: K8sManager = None

    def __init__(
        self,
        controllers: Optional[List[Controller]],
        instance: Optional[Dict[str, ModuleType]],
        debug: bool=False,
        test: bool=False,
        *args,
        **kwargs
    ):
        self.scope = Scope.PROD
        if debug:
            self.scope |= Scope.DEBUG
        if test:
            self.scope |= Scope.TEST

        ## Instance Info.
        self.tables: ModuleType = instance.get('tables')
        self.schemas: ModuleType = instance.get('schemas')

        m = instance.get('manifests')
        if m:
            config.K8_MANIFESTS = m

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
        self.controllers = []
        classes = CORE_CONTROLLERS + controllers or []
        classes.append(K8sController)
        routes = self.adopt_controllers(classes)

        ## Schema Generator.
        self.schema_generator = SchemaGenerator(
            {
                "openapi": "3.0.0", "info": {
                    "name": config.API_NAME,
                    "version": config.API_VERSION,
                    "backend": "biodm",
                    "backend_version": CORE_VERSION
                }
            }
        )

        """Headless Services

            For entities that are managed internally: not exposing routes.
            i.e. only ListGroups and History atm

            Since the controller normally instanciates the service, and it does so
            because the services needs to access the app instance.
            If more useful cases for this show up we might want to design a cleaner solution.
        """
        History.svc = UnaryEntityService(app=self, table=History)
        ListGroup.svc = CompositeEntityService(app=self, table=ListGroup)

        super().__init__(routes=routes, debug=Scope.DEBUG in self.scope, *args, **kwargs)

        ## Middlewares
        self.add_middleware(HistoryMiddleware, server_host=config.SERVER_HOST)
        self.add_middleware(
            CORSMiddleware, allow_credentials=True,
            allow_origins=(
                [config.SERVER_HOST, "*"] + (
                    [config.KC_HOST]
                    if hasattr(config, "KC_HOST")
                    else []
                )
            ),
            allow_methods=["*"],
            allow_headers=["*"],
            # max_age=10 # TODO: max age cache in config.
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
    def server_endpoint(self):
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

    def deploy_managers(self):
        """Conditionally deploy managers. Each manager connects to an external service.
        Appart from the DB, managers are optional, with respect to config population.
        """
        # Always deploy DB.
        self.db = DatabaseManager(app=self)

        # S3_ENDPOINT_URL
        # S3_BUCKET_NAME
        # S3_ACCESS_KEY_ID
        # S3_SECRET_ACCESS_KEY 

        for name, mngr in zip(
            ("kc", "s3", "k8"), (KeycloakManager, S3Manager, K8sManager)
        ):
            # Get config entries for that manager.
            c = self._parse_config(name)
            if c:
                self.__dict__[name] = mngr(app=self, **c)
                self.logger.info(f"{name.upper()} manager UP.")

    def adopt_controllers(self, controllers: List[Controller]) -> List:
        """Adopts controllers, and their associated routes."""
        routes = []
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
