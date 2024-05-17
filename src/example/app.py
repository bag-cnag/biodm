#!/usr/bin/env python
import uvicorn

from biodm.api import Api

from entities import tables, schemas
from entities import controllers 
# from example import manifests
import config


def main():
    app = Api(
        debug=config.DEBUG, 
        controllers=controllers.CONTROLLERS,
        instance={
            'config': config,
            'tables': tables,
            'schemas': schemas,
            # 'manifests': manifests
        }
    )
    return app


if __name__ == "__main__":
    uvicorn.run(
        f"{__name__}:main",
        factory=True,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        loop="uvloop",
        # reload=config.DEV,
        log_level="debug" if config.DEBUG else "info",
        access_log=False
    )
