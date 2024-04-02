from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, UUID


from core.components.controllers import ActiveController, AdminController
from core.components.services import KCService, KCGroupService, KCUserService
from core.tables import Group, User
from core.components.table import Base


# class KCController(AdminController):
class KCController(ActiveController):
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


class UserSchema(Schema):
    class Meta:
        model = User
        include_fk = True
        load_instance = True

    id = UUID(required=True)
    username = String(required=True)
    password = String()
    email = String()
    first_name = String()
    last_name = String()

    groups = List(Nested('GroupSchema'), load_only=True)

class GroupSchema(Schema):
    class Meta:
        model = Group
        include_fk = True
        load_instance = True

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
    users = List(Nested('UserSchema'), load_only=True)

class UserController(KCController):
    def __init__(self):
        super().__init__(
              entity="User",
              table=User,
              schema=UserSchema)


class GroupController(KCController):
    def __init__(self):
        super().__init__(
              entity="Group",
              table=Group,
              schema=GroupSchema)


CORE_CONTROLLERS = [UserController, GroupController]
