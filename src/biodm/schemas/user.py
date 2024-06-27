from marshmallow import Schema, pre_load
from marshmallow.fields import String, List, Nested


class UserSchema(Schema):
    """Schema for Keycloak Users. id field is purposefully left out as we manage it internally."""
    username = String(required=True)
    password = String(load_only=True)
    email = String()
    first_name = String()
    last_name = String()

    groups = List(Nested('GroupSchema', exclude=('parent', 'users',)))
