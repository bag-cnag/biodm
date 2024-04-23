
from marshmallow import Schema, validate, pre_load, ValidationError
from marshmallow.fields import String, Date, List, Nested, Integer, UUID

from .group import GroupSchema


class ListGroupSchema(Schema):
    id = Integer()
    # groups = List(Nested(GroupSchema), only=('name', 'n_members',), required=True)
    groups = List(Nested('GroupSchema', only=('name', 'n_members',)), required=True)

