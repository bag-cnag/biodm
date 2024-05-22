from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer


class GroupSchema(Schema):
    """Schema for Keycloak Groups. id field is purposefully left out as we manage it internally."""
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

    parent = Nested('GroupSchema', exclude=['parent', 'users']) #lambda: UserSchema()
    users = List(Nested('UserSchema', exclude=['groups']))
