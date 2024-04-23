#!/usr/bin/env python
import uvicorn

from biodm.api import Api
from biodm.basics import CORE_CONTROLLERS

from example.entities.controllers import CONTROLLERS
import example.config as config

def main():
    app = Api(
        config=config,
        debug=config.DEBUG, 
        routes=[],
        controllers=CORE_CONTROLLERS+CONTROLLERS,
    )
    return app


if __name__ == "__main__":
    uvicorn.run(
        f"{__name__}:main",
        factory=True,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="debug" if config.DEBUG else "info"
    )
