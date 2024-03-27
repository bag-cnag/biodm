from marshmallow import Schema
from marshmallow.fields import List, Nested, UUID, String

from instance.entities.tables import User
# from controllers import schemas
# from . import GroupSchema


class UserSchema(Schema):
    class Meta:
        model = User

    id = UUID()
    username = String(required=True)
    password = String(required=True)
    email = String()
    first_name = String()
    last_name = String()


    groups = List(Nested('GroupSchema'), load_only=True)
