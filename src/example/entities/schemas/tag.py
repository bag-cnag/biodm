from marshmallow import Schema
from marshmallow.fields import String, List, Nested, Integer

# from controllers import schemas
from .dataset import DatasetSchema


class TagSchema(Schema):
    name = String(required=True)

    # datasets = List(Nested(DatasetSchema))
