#!/usr/bin/env python
import logging
# from asyncio import run as arun
from typing import List

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Route, Router

import config
from api.routes import routes
from model import DatabaseManager
from controllers import Controller, TagController # , HttpMethod
from exceptions import RequestError
from errors import onerror

# from controllers import schemas
# from model.tables import group, user, dataset, tag
# from model.tables import group


class Api(Starlette):
    logger = logging.getLogger(__name__)

    def __init__(self, controllers=[], routes=[], *args, **kwargs):
        self.db = DatabaseManager()
        self.controllers = []
        # self.controllers = controllers if controllers else []
        ctrl_routes = self.adopt_controllers(controllers)
        routes.extend(ctrl_routes)
        super(Api, self).__init__(routes=routes, *args, **kwargs)

        # Set up CORS
        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
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
            self.controllers.append(c)
        return routes
            # for part_uri, method, coroutine in routes:
            #     print(ressource + part_uri)
            #     self.routes.append(
            #         Route(
            #             ressource + part_uri,
            #             coroutine,
            #             [method.value]
            #         )
            #     )
                # self.add_route(
                #     ressource + part_uri,
                #     coroutine,
                #     [method.value]
                # )

            # Keep Track of controllers.


    async def onstart(self) -> None:
        if config.DEV:
            """Dev mode: drop all and create tables."""
            await self.db.init_db()


# async def main():
#     await app.db.init_db()
#     # await test_entities()
#     # await test_2(proj)
    # await uvicorn.run(app)

def main():
    app = Api(
        debug=config.DEBUG, 
        routes=routes,
        controllers=[TagController]
    )
    ## Middlewares
    # app.add_middleware(AuthenticationMiddleware, callback_url="http://localhost:8000/kc/callback", redirect_uri="/howdy", logout_uri="/logout")
    app.add_middleware(SessionMiddleware, secret_key="r4nD0m_p455")
    return app

if __name__ == "__main__":
    uvicorn.run(
        f"{__name__}:main",
        factory=True,
        # TODO:
        # host=
        # port=
        log_level="debug" if config.DEBUG else "info"
    )
