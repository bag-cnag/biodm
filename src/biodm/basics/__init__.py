from .rootcontroller import RootController
from .usercontroller import UserController
from .groupcontroller import GroupController
from .k8scontroller import K8sController

CORE_CONTROLLERS = [RootController, UserController, GroupController]
