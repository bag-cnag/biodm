# from marshmallow import Schema
from marshmallow.fields import String, List, Nested, Integer

from biodm.components import Schema


class ProjectSchema(Schema):
    id = Integer()
    name = String()
    description = String()

    datasets = List(Nested('DatasetSchema'))
