from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, UUID


from core.components.controllers import AdminController
from core.components.services import KCService, KCGroupService, KCUserService
from core.tables import Group, User
from core.components.table import Base


class KCController(AdminController):
    """Controller for entities managed by keycloak (i.e. User/Group)."""
    def _infer_svc(self) -> KCService:
        e = self.entity.lower()
        if 'user' in e:
            return KCUserService
        elif 'group' in e:
            return KCGroupService
        else:
            raise ValueError("KCController manages keycloak user/groups only. "
                             "Use that class on corresponding entities.")


class UserController(KCController):
    class UserSchema(Schema):
        id = UUID()
        username = String(required=True)
        password = String(required=True)
        email = String()
        first_name = String()
        last_name = String()

        groups = List(Nested('GroupController.GroupSchema'), load_only=True)

    def __init__(self):
        super().__init__(
              entity="User",
              table=User,
              schema=self.UserSchema)


class GroupController(KCController):
    class GroupSchema(Schema):
        name = String(required=True)
        # Test
        n_members = Integer(required=False)

        name_parent = String(
            required=False,
            # Important for bulk insert into
            load_default=None 
            # validate=validate.OneOf(
            #     [g.name for g in Group]
            # )
        )

        parent = Nested('GroupSchema', load_only=True)
        users = List(Nested(UserController.UserSchema), load_only=True)

    def __init__(self):
        super().__init__(
              entity="Group",
              table=Group,
              schema=self.GroupSchema)


CORE_CONTROLLERS = [UserController, GroupController]
