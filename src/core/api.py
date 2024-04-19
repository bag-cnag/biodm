from asyncio import wait_for, TimeoutError
import logging
from typing import List

# from keycloak.extensions.starlette import AuthenticationMiddleware
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
# from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route
from starlette.schemas import SchemaGenerator

from core.components.managers import DatabaseManager, KeycloakManager, S3Manager
from core.components.controllers import Controller
from core.components.services import UnaryEntityService, CompositeEntityService
from core.errors import onerror
from core.exceptions import RequestError
from core.utils.utils import to_it
from core.utils.security import extract_and_decode_token, auth_header
from core.tables import History, ListGroup

from instance import config


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Emit timeout signals."""
    async def dispatch(self, request, call_next):
        try:
            return await wait_for(
                call_next(request), 
                timeout=config.SERVER_TIMEOUT)
        except TimeoutError:
            return HTMLResponse("Request reached timeout.", status_code=504)


class HistoryMiddleware(BaseHTTPMiddleware):
    """Logins in authenticated user requests in History."""
    async def dispatch(self, request: Request, call_next) -> Response:
        if auth_header(request):
            app = History.svc.app
            username, _, _ = await extract_and_decode_token(app.kc, request)
            h = {
                'username_user': username,
                'endpoint': str(request.url).split(config.SERVER_HOST)[-1],
                'method': request.method,
                'content': "" # await request.body() # TODO: ask ivo.
            }
            await History.svc.create(h, stmt_only=False, serializer=None)
        return await call_next(request)


class Api(Starlette):
    logger = logging.getLogger(__name__)

    def __init__(self, controllers=[], routes=[], *args, **kwargs):
        ## Managers
        self.db = DatabaseManager()
        self.kc = KeycloakManager()
        self.s3 = S3Manager(app=self)

        ## Controllers
        self.controllers = []
        routes.extend(self.adopt_controllers(controllers))

        ## Schema Generator
        # TODO: take from config
        self.schema_generator = SchemaGenerator(
           {"openapi": "3.0.0", "info": {"title": "biodm", "version": "0.1.0"}}
        )

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
        self.add_middleware(HistoryMiddleware)
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
            self.add_middleware(TimeoutMiddleware)

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
        if config.DEV:
            """Dev mode: drop all and create tables."""
            await self.db.init_db()
