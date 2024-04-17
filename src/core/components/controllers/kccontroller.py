from core.components.controllers import ResourceController, AdminController
from core.components.services import KCService, KCUserService, KCGroupService
from core.exceptions import ImplementionErrror


# class KCController(AdminController):
class KCController(ResourceController):
    """Controller for entities managed by keycloak (i.e. User/Group)."""
    def _infer_svc(self) -> KCService:
        match self.entity.lower():
            case "user":
                return KCUserService
            case "group":
                return KCGroupService
            case _:
                raise ImplementionErrror("KCController currently only support User/Groups.")
