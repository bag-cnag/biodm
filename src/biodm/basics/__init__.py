from .rootcontroller import RootController
from .k8scontroller import K8sController # Not below, because started conditionally.

from biodm.components.controllers import ResourceController


class UserController(ResourceController):
    """User Controller."""
    pass


class GroupController(ResourceController):
    """Group Controller."""
    pass


CORE_CONTROLLERS = [RootController, UserController, GroupController]
