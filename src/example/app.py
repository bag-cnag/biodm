#!/usr/bin/env python
import os
import sys
from typing import Literal
# from pathlib import Path
import uvicorn

from biodm import config
from biodm.api import Api


sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from entities import controllers

# sys.path.append(Path(__file__).parent)
# import controllers
# from . import entities
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
        loop: Literal['uvloop'] = "uvloop"
    except ImportError:
        loop: Literal['auto'] = "auto"

    uvicorn.run(
        f"{__name__}:main",
        factory=True,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        loop=loop,
        log_level="debug", # or "info"
        access_log=False
    )
