# from marshmallow import Schema
from marshmallow.fields import List, Nested, Integer

from biodm.components import Schema
from .group import GroupSchema

class ListGroupSchema(Schema):
    id = Integer()
    groups = List(Nested(lambda: GroupSchema(load_only=['users', 'children', 'parent'])))
