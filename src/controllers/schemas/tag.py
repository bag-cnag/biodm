from marshmallow import Schema
from marshmallow.fields import String, List, Nested, Integer

from model.tables import Tag
# from controllers import schemas
from .dataset import DatasetSchema


class TagSchema(Schema):
    class Meta:
        model = Tag

    id = Integer()
    name = String(required=True)

    # datasets = List(Nested(DatasetSchema))
