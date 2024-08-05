from marshmallow import Schema, validate, pre_load, ValidationError
from marshmallow.fields import String, Date, List, Nested, Integer, UUID



class DatasetSchema(Schema):
    id = Integer()
    version = Integer()
    name = String()
    description = String(required=False)
    # name_owner_group = String(
    #     required=True, 
    #     # validate=validate.OneOf(
    #     #     [g.name for g in Group]
    #     # )
    # )
    username_user_contact = String(required=True) # required=True
    id_project = Integer(required=True) # required=True

    # owner_group = Nested('GroupSchema') # , only=('path', 'n_members',)
    contact = Nested('UserSchema') # , only=('username', )
    project = Nested('ProjectSchema', exclude=('datasets', ))
    tags = List(Nested('TagSchema'))
    files = List(Nested('FileSchema'))

    # id_ls_download = Integer()
    # ls_download = Nested('ListGroupSchema')
