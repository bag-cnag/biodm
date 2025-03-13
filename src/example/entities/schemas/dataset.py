from marshmallow import Schema #, validate, pre_load, ValidationError
from marshmallow.fields import String, Date, List, Nested, Integer, UUID, Boolean

from biodm.schemas import UserSchema
from .project import ProjectSchema

class DatasetSchema(Schema):
    id = Integer()
    version = Integer()
    is_latest = Boolean(dump_only=True)

    name = String()
    description = String()

    contact_username = String()
    project_id = Integer()

    # owner_group = Nested('GroupSchema')
    # contact = Nested('UserSchema')
    contact = Nested(lambda: UserSchema(load_only=['groups']))

    project = Nested(lambda: ProjectSchema(load_only=['datasets']))
    tags = List(Nested('TagSchema'))
    files = List(Nested('FileSchema'))

    # id_ls_download = Integer()
    # ls_download = Nested('ListGroupSchema')
