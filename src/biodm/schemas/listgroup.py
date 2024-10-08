from marshmallow import Schema
from marshmallow.fields import List, Nested, Integer


class ListGroupSchema(Schema):
    id = Integer()
    groups = List(Nested('GroupSchema', exclude=['users', 'children', 'parent']))
