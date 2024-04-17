from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, UUID


class UserSchema(Schema):
    """Schema for Keycloak Users. 
       id field is purposefully left out as it is managed internally."""
    # class Meta:
    #     model = User
    #     include_fk = True
    #     load_instance = True
    # id = UUID()
    username = String(required=True)
    password = String()
    email = String()
    first_name = String()
    last_name = String()

    groups = List(Nested('GroupSchema'))
