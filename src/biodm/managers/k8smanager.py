from __future__ import annotations
import time
from typing import Tuple

from kubernetes import client

from typing import TYPE_CHECKING


# from biodm.exceptions import 

if TYPE_CHECKING:
    from biodm.api import Api


class K8sManager:
    def __init__(self, app: Api) -> None:
        self.app = app
