#!/usr/bin/env python
import logging
# from asyncio import run as arun
from typing import List
import requests
import json


import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from keycloak.extensions.starlette import AuthenticationMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.routing import Route, Router

import config
from security import login_required
from api.routes import routes
from model import DatabaseManager
from controllers import (
    Controller, 
    TagController,
    UserController, 
    GroupController,
    DatasetController
)
from exceptions import RequestError
from errors import onerror

class Api(Starlette):
    logger = logging.getLogger(__name__)

    def __init__(self, controllers=[], routes=[], *args, **kwargs):
        self.db = DatabaseManager()
        self.controllers = []
        routes.extend(self.adopt_controllers(controllers))
        super(Api, self).__init__(routes=routes, *args, **kwargs)

        # Set up CORS
        self.add_middleware(
            CORSMiddleware, allow_credentials=True,
            allow_origins=["*, http://127.0.0.1"], allow_methods=["*"], allow_headers=["*"]
        )

        # Event handlers
        self.add_event_handler("startup", self.onstart)
        # self.add_event_handler("shutdown", self.on_app_stop)

        # Error handlers
        self.add_exception_handler(RequestError, onerror)
        # self.add_exception_handler(DatabaseError, on_error)
        # self.add_exception_handler(Exception, on_error)

    def adopt_controllers(self, controllers: List[Controller]) -> None:
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

    async def onstart(self) -> None:
        if config.DEV:
            """Dev mode: drop all and create tables."""
            await self.db.init_db()

def main():
    handshake = "http://127.0.0.1:8000/syn_ack"

    # Setup some basic auth system:
    async def login(_):
        """Returns the url for keycloak login page."""
        login_url = (
            f"{config.KC_HOST}/auth/realms/{config.KC_REALM}/"
            "protocol/openid-connect/auth?"
            "scope=openid" "&response_type=code"
            f"&client_id={config.CLIENT_ID}"
            f"&redirect_uri={handshake}"
        )
        return PlainTextResponse(login_url + "\n")


    async def syn_ack(request):
        """Login callback function when the user logs in through the browser.

            We get an authorization code that we redeem to keycloak for a token.
            This way the client_secret remains hidden to the user.
        """
        code = request.query_params['code']

        kc_token_url = (
            f"{config.KC_HOST}/auth/realms/{config.KC_REALM}/"
            "protocol/openid-connect/token?"
        )
        r = requests.post(kc_token_url,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'authorization_code',
                'client_id': config.CLIENT_ID,
                'client_secret': config.CLIENT_SECRET,
                'code': code,
                # !! Must be the same as in /login
                'redirect_uri': f'{handshake}'
            }
        )
        if r.status_code != 200:
            raise RuntimeError(f"keycloak token handshake failed: {r.text} {r.status_code}")

        return PlainTextResponse(json.loads(r.text)['access_token'] + '\n')


    @login_required
    async def authenticated(userid, groups, projects):
        return PlainTextResponse(f"{userid}, {groups}, {projects}\n")


    # async def logout(_):
    #     return PlainTextResponse("User logged out!")

    routes.append(Route("/login", endpoint=login))
    routes.append(Route("/syn_ack", endpoint=syn_ack))
    routes.append(Route("/authenticated", endpoint=authenticated))
    # routes.append(Route("/logout", endpoint=logout))

    ## Instanciate app with a controller for each entity
    app = Api(
        debug=config.DEBUG, 
        routes=routes,
        controllers=[
            TagController,
            UserController,
            GroupController,
            DatasetController,
        ]
    )
    ## Middlewares
    # app.add_middleware(AuthenticationMiddleware, callback_url=callback, login_redirect_uri="/get_token", logout_uri="/logout")
    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
    return app


if __name__ == "__main__":
    uvicorn.run(
        f"{__name__}:main",
        factory=True,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="debug" if config.DEBUG else "info"
    )
