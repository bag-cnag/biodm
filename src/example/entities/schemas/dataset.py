from marshmallow import Schema #, validate, pre_load, ValidationError
from marshmallow.fields import String, Date, List, Nested, Integer, UUID


class DatasetSchema(Schema):
    id = Integer()
    version = Integer()
    name = String()
    description = String()
    # name_owner_group = String(
    #     required=True, 
    #     # validate=validate.OneOf(
    #     #     [g.name for g in Group]
    #     # )
    # )
    username_contact = String()
    id_project = Integer()

    # owner_group = Nested('GroupSchema') # , only=('path', 'n_members',)
    contact = Nested('UserSchema', exclude=['groups']) # , only=('username', )
    project = Nested('ProjectSchema', exclude=('datasets', ))
    tags = List(Nested('TagSchema'))
    files = List(Nested('FileSchema'))

    # id_ls_download = Integer()
    # ls_download = Nested('ListGroupSchema')
