#!/usr/bin/env python
import uvicorn

from core.api import Api
from core.basics import CORE_CONTROLLERS
from instance import config
from instance.entities.controllers import CONTROLLERS


def main():
    app = Api(
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
