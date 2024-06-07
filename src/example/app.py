#!/usr/bin/env python
import uvicorn

from biodm import config
from biodm.api import Api

from entities import controllers
# from example import manifests


def main():
    app = Api(
        controllers=controllers.CONTROLLERS,
        instance={
            # 'manifests': manifests
        },
        debug=True,
        test=False
    )
    return app


if __name__ == "__main__":
    try:
        import uvloop as _
        loop="uvloop"
    except ImportError:
        loop="auto"

    uvicorn.run(
        f"{__name__}:main",
        factory=True,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        loop=loop,
        log_level="debug", # or "info"
        access_log=False
    )
