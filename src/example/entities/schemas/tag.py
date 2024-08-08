from marshmallow import Schema
from marshmallow.fields import String, List, Nested, Integer

# from controllers import schemas
from .dataset import DatasetSchema


class TagSchema(Schema):
    name = String()

    # datasets = List(Nested(DatasetSchema))
