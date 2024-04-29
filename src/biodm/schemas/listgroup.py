from marshmallow import Schema
from marshmallow.fields import List, Nested, Integer


class ListGroupSchema(Schema):
    id = Integer()
    groups = List(Nested('GroupSchema', only=('name', 'n_members',)), required=True)
