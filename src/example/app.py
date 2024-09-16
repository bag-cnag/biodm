#!/usr/bin/env python
from typing import Literal
import uvicorn

from biodm import config
from biodm.api import Api

from entities import tables as _ # import tables first to avoid duplicate imports.
from entities import controllers
import manifests


def main():
    app = Api(
        controllers=controllers.CONTROLLERS,
        manifests=manifests.MANIFESTS,
        debug=True,
        test=False
    )
    return app


if __name__ == "__main__":
    loop: Literal['uvloop', 'auto']
    try:
        import uvloop as _
        loop = "uvloop"
    except ImportError:
        loop = "auto"

    uvicorn.run(
        f"{__name__}:main",
        factory=True,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        loop=loop,
        log_level="debug", # or "info"
        access_log=False
    )
