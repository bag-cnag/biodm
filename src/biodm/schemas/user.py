from marshmallow import Schema
from marshmallow.fields import String, List, Nested


class UserSchema(Schema):
    """Schema for Keycloak Users. 
       id field is purposefully left out as it is managed internally."""
    username = String(required=True)
    password = String()
    email = String()
    first_name = String()
    last_name = String()

    groups = List(Nested('GroupSchema'))
