from marshmallow import Schema
from marshmallow.fields import String, List, Nested

from .user import UserSchema

class GroupSchema(Schema):
    """Schema for Keycloak Groups. id field is purposefully left out as we manage it internally."""
    path = String(metadata={"description": "Group name chain separated by '__'"})

    users = List(Nested(lambda: UserSchema(load_only=['groups'])))
    children = List(Nested(lambda: GroupSchema(load_only=['users', 'children', 'parent'])))
    parent = Nested('GroupSchema', dump_only=True)
