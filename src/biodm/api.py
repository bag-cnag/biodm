from asyncio import wait_for, TimeoutError
import logging
import logging.config
from typing import List

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route
from starlette.schemas import SchemaGenerator
from starlette.types import ASGIApp

from biodm.basics import CORE_CONTROLLERS
from biodm.components.managers import DatabaseManager, KeycloakManager, S3Manager
from biodm.components.controllers import Controller
from biodm.components.services import UnaryEntityService, CompositeEntityService
from biodm.errors import onerror
from biodm.exceptions import RequestError
from biodm.utils.utils import to_it
from biodm.utils.security import extract_and_decode_token, auth_header
from biodm.tables import History, ListGroup
from biodm import __version__ as CORE_VERSION


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Emit timeout signals."""
    def __init__(self, app: ASGIApp, timeout: int=30) -> None:
        self.timeout = timeout
        super().__init__(app, self.dispatch)

    async def dispatch(self, request, call_next):
        try:
            return await wait_for(
                call_next(request), 
                timeout=self.timeout)
        except TimeoutError:
            return HTMLResponse("Request reached timeout.", status_code=504)


class HistoryMiddleware(BaseHTTPMiddleware):
    """Logins in authenticated user requests in History."""
    def __init__(self, app: ASGIApp, server_host: str) -> None:
        self.server_host = server_host
        super().__init__(app, self.dispatch)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        if auth_header(request):
            app = History.svc.app
            username, _, _ = await extract_and_decode_token(app.kc, request)
            body = await request.body()
            h = {
                'username_user': username,
                'endpoint': str(request.url).split(self.server_host)[-1],
                'method': request.method,
                'content': body if body else ""
            }
            await History.svc.create(h, stmt_only=False, serializer=None)
        return await call_next(request)


class Api(Starlette):
    logger = logging.getLogger(__name__)

    def __init__(self, config=None, controllers=[], routes=[], tables=None, schemas=None, *args, **kwargs):
        self.tables = tables
        self.schemas = schemas
        self.config = config

        ## Managers
        self.db = DatabaseManager(app=self)
        self.kc = KeycloakManager(app=self)
        self.s3 = S3Manager(app=self)

        ## Controllers
        self.controllers = []
        routes.extend(self.adopt_controllers(controllers + CORE_CONTROLLERS))

        ## Schema Generator
        self.schema_generator = SchemaGenerator({
            "openapi": "3.0.0", "info": {
                "name": config.API_NAME, 
                "version": config.API_VERSION, 
                "backend": "biodm", 
                "backend_version": CORE_VERSION
        }})

        ## Headless Services
        """For entities that are managed internally: not exposing routes 
            i.e. only ListGroups and History atm

            Since the controller normally instanciates the service, and it does so
            because the services needs to access the app instance.
            If more useful cases for this show up we might want to design a cleaner solution.
        """
        History.svc = UnaryEntityService(app=self, table=History, pk=('timestamp', 'username_user'))
        ListGroup.svc = CompositeEntityService(app=self, table=ListGroup, pk=('id',))

        super(Api, self).__init__(routes=routes, *args, **kwargs)

        ## Middlewares
        # History
        self.add_middleware(HistoryMiddleware, server_host=config.SERVER_HOST)
        # CORS
        self.add_middleware(
            CORSMiddleware, allow_credentials=True,
            allow_origins=[config.SERVER_HOST, config.KC_HOST, "*"], 
            allow_methods=["*"], allow_headers=["*"]
        )
        # Session ?
        # app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
        # Request timeout in production
        if not config.DEV:
            self.add_middleware(TimeoutMiddleware, timeout=config.SERVER_TIMEOUT)

        # Event handlers
        self.add_event_handler("startup", self.onstart)
        # self.add_event_handler("shutdown", self.on_app_stop)

        # Error handlers
        self.add_exception_handler(RequestError, onerror)
        # self.add_exception_handler(DatabaseError, on_error)
        # self.add_exception_handler(Exception, on_error)

    # def scan_entities(self, ) -> List[Controller]:
    #     """Make a pass over entities defined in instance to infer controllers"""
    # TODO ?
    #     ls = []
    #     return ls

    def adopt_controllers(self, controllers: List[Controller]=[]) -> List:
        """Adopts controllers, and their associated routes."""
        routes = []
        for controller in controllers:
            # Instanciate.
            c = controller.init(app=self)
            # Fetch and add routes.
            routes.extend(to_it(c.routes()))
            # Keep Track of controllers.
            self.controllers.append(c)
        return routes

    async def onstart(self) -> None:
        if self.config.DEV:
            """Dev mode: drop all and create tables."""
            await self.db.init_db()
