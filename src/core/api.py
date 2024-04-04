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

from core.basics.login import login, syn_ack, authenticated
from core.components.managers import DatabaseManager, KeycloakManager
from core.components.controllers import Controller
from core.errors import onerror
from core.exceptions import RequestError
from core.utils.security import extract_and_decode_token, auth_header
from core.tables import History

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
            userid, _, _ = extract_and_decode_token(request)
            async with self.app.db.session() as session:
                entry = History({})
                # TODO:
        return await call_next(request)


class Api(Starlette):
    logger = logging.getLogger(__name__)

    def __init__(self, controllers=[], routes=[], *args, **kwargs):
        self.db = DatabaseManager()
        self.kc = KeycloakManager(app=self)
        self.controllers = []
        # routes.extend(self.adopt_controllers(
        #     self.scan_entities()))
        routes.extend(self.adopt_controllers(controllers))
        routes.extend(self.setup_login())

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
    #     """Makes a pass over entities defined in instance to infer controllers"""
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
            routes.append(c.routes())
            # Keep Track of controllers.
            self.controllers.append(c)
        return routes

    def setup_login(self) -> List:
        """Setup login routes."""
        return [
            Route("/login", endpoint=login),
            Route("/syn_ack", endpoint=syn_ack),
            Route("/authenticated", endpoint=authenticated)
        ]

    async def onstart(self) -> None:
        if config.DEV:
            """Dev mode: drop all and create tables."""
            await self.db.init_db()
