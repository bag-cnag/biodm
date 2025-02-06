# from marshmallow import Schema
from marshmallow.fields import String, List, Nested

from biodm.components import Schema


class UserSchema(Schema):
    """Schema for Keycloak Users. id field is purposefully left out as we manage it internally."""
    username = String()
    password = String(load_only=True)
    email = String()
    firstName = String()
    lastName = String()

    def dump_group(): # Delay import using a function.
        from .group import GroupSchema
        return GroupSchema(load_only=['users', 'children', 'parent'])

    groups = List(Nested(dump_group))
