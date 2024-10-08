from marshmallow import Schema
from marshmallow.fields import String, List, Nested


class UserSchema(Schema):
    """Schema for Keycloak Users. id field is purposefully left out as we manage it internally."""
    username = String()
    password = String(load_only=True)
    email = String()
    firstName = String()
    lastName = String()

    groups = List(Nested('GroupSchema', exclude=['users', 'children', 'parent']))
