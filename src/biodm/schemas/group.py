from marshmallow import Schema, validate, pre_load
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

    parent = Nested('GroupSchema', exclude=['parent', 'users'])
    users = List(Nested('UserSchema', exclude=['groups']))


    @pre_load
    def pre_load_process(self, data, many, **kwargs):
        ret = data

        name_parent = data.get('name_parent')
        parent_name = data.get('parent', {}).get('name')

        if name_parent and parent_name:
            assert(name_parent == parent_name)
        elif parent_name and not name_parent:
            ret["name_parent"] = parent_name

        return ret
