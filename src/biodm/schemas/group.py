from marshmallow import Schema #, validate
from marshmallow.fields import String, List, Nested, Integer


class GroupSchema(Schema):
    """Schema for Keycloak Groups. id field is purposefully left out as we manage it internally."""
    path = String(metadata={"description": "Group name chain separated by '__'"})
    # Test
    n_members = Integer()

    users = List(Nested('UserSchema', exclude=['groups'])) # only=['username']
    children = List(Nested('GroupSchema', exclude=['children', 'parent'])) # exclude=['users', 'children', 'parent']))
    parent = Nested('GroupSchema', exclude=['children', 'parent'])# exclude=['users', 'children', 'parent'], dump_only=True) # parent', 'users', 'children
