import time
from typing import Tuple

from kubernetes import client
from biodm.components import Component


class K8sManager(Component):
    """"""