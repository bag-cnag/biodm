#!/usr/bin/env python
import os
import sys
import uvicorn

from biodm.api import Api

from example.entities.controllers import CONTROLLERS
from example.entities import tables, schemas
sys.path.append(os.path.join(os.path.dirname(__file__), "config"))
import config


def main():
    app = Api(
        config=config,
        debug=config.DEBUG, 
        routes=[],
        controllers=CONTROLLERS,
        tables=tables,
        schemas=schemas
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
