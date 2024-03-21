from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, Bool

from model.tables import File
from .dataset import DatasetSchema


class FileSchema(Schema):
    class Meta:
        model = File

    id = Integer()
    filename = String(required=True)
    url = String(required=False)
    ready = Bool(required=False)
    id_dataset = Integer(required=True)
    version_dataset = Integer(required=True)
    dataset = Nested(DatasetSchema, required=True, load_only=True)
