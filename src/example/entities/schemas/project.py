from marshmallow import Schema
from marshmallow.fields import String, List, Nested, Integer


class ProjectSchema(Schema):
    id = Integer()
    name = String(required=True)
    description = String(required=False)

    datasets = List(Nested('DatasetSchema'))
