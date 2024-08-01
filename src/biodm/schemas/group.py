from marshmallow import Schema, validate, pre_load
from marshmallow.fields import String, List, Nested, Integer


class GroupSchema(Schema):
    """Schema for Keycloak Groups. id field is purposefully left out as we manage it internally."""
    path = String(required=True, metadata={"description": "Group name chain separated by '__'"})
    # Test
    n_members = Integer(required=False)

    users = List(Nested('UserSchema', exclude=['groups'])) # only=['username']
    children = List(Nested('GroupSchema', exclude=['children', 'parent'])) # exclude=['users', 'children', 'parent']))
    parent = Nested('GroupSchema', exclude=['children', 'parent'])# exclude=['users', 'children', 'parent'], dump_only=True) # parent', 'users', 'children

    # @pre_load
    # def pre_load_process(self, data, many, **kwargs):
    #     ret = data

    #     path_parent = data.get('path_parent')
    #     parent_path = data.get('parent', {}).get('path')

    #     if path_parent and parent_path:
    #         assert(path_parent == parent_path)
    #     elif parent_path and not path_parent:
    #         ret["path_parent"] = parent_path

    #     for child in data.get('children', []):
    #         child["path_parent"] = data["path"]

    #     return ret
