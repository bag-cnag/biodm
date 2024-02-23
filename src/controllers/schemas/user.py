from marshmallow import Schema
from marshmallow.fields import List, Nested, UUID

from model.tables import User
# from controllers import schemas
# from . import GroupSchema


class UserSchema(Schema):
    class Meta:
        model = User

    id = UUID(required=True)
    groups = List(Nested('GroupSchema'), load_only=True)
