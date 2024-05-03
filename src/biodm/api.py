from asyncio import wait_for, TimeoutError
import logging
import logging.config
from typing import List, Optional

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route
from starlette.schemas import SchemaGenerator
from starlette.types import ASGIApp
from starlette.config import Config

from biodm.basics import CORE_CONTROLLERS, k8scontroller
from biodm.managers import DatabaseManager, KeycloakManager, S3Manager, K8sManager
from biodm.components.controllers import Controller
from biodm.components.services import UnaryEntityService, CompositeEntityService
from biodm.error import onerror
from biodm.exceptions import RequestError
from biodm.utils.utils import to_it
from biodm.utils.security import extract_and_decode_token, auth_header
from biodm.tables import History, ListGroup
from biodm import __version__ as CORE_VERSION
try:
    import kubernetes
    HAS_K8s = True
except:
    HAS_K8s = False


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Emit timeout signals."""
    def __init__(self, app: ASGIApp, timeout: int=30) -> None:
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
        if auth_header(request):
            app = History.svc.app
            username, _, _ = await extract_and_decode_token(app.kc, request)
            body = await request.body()
            entry = {
                'username_user': username,
                'endpoint': str(request.url).rsplit(self.server_host, maxsplit=1)[-1],
                'method': request.method,
                'content': body if body else ""
            }
            await History.svc.create(entry, stmt_only=False)
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

    def __init__(self,
                 config: Config,
                 controllers: Optional[List[Controller]]=None,
                 tables=None,
                 schemas=None,
                 *args,
                 **kwargs
    ):
        ## Instance Info.
        self.tables = tables
        self.schemas = schemas
        self.config = config

        ## Managers.
        self.db = DatabaseManager(app=self)
        self.kc = KeycloakManager(app=self)
        self.s3 = S3Manager(app=self)
        if HAS_K8s:
            self.k8s = K8sManager(app=self)

        ## Controllers.
        self.controllers = []
        routes = []
        routes.extend(
            self.adopt_controllers(
                CORE_CONTROLLERS  +
                controllers or [] +
                [k8scontroller] if HAS_K8s else []
            )
        )

        ## Schema Generator.
        self.schema_generator = SchemaGenerator({
            "openapi": "3.0.0", "info": {
                "name": config.API_NAME, 
                "version": config.API_VERSION, 
                "backend": "biodm", 
                "backend_version": CORE_VERSION
        }})

        """Headless Services

            For entities that are managed internally: not exposing routes 
            i.e. only ListGroups and History atm

            Since the controller normally instanciates the service, and it does so
            because the services needs to access the app instance.
            If more useful cases for this show up we might want to design a cleaner solution.
        """
        History.svc = UnaryEntityService(app=self, table=History)
        ListGroup.svc = CompositeEntityService(app=self, table=ListGroup)

        super(Api, self).__init__(routes=routes, *args, **kwargs)

        ## Middlewares
        self.add_middleware(HistoryMiddleware, server_host=config.SERVER_HOST)
        self.add_middleware(
            CORSMiddleware, allow_credentials=True,
            allow_origins=[config.SERVER_HOST, config.KC_HOST, "*"], 
            allow_methods=["*"], allow_headers=["*"]
        )
        if not config.DEV:
            self.add_middleware(TimeoutMiddleware, timeout=config.SERVER_TIMEOUT)

        # Event handlers
        self.add_event_handler("startup", self.onstart)
        # self.add_event_handler("shutdown", self.on_app_stop)

        # Error handlers
        self.add_exception_handler(RequestError, onerror)
        # self.add_exception_handler(DatabaseError, on_error)
        # self.add_exception_handler(Exception, on_error)

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
        if self.config.DEV:
            """Dev mode: drop all and create tables."""
            await self.db.init_db()
