from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, Bool


class FileSchema(Schema):
    id = Integer()
    filename = String(required=True)
    url = String(required=False)
    ready = Bool(required=False)
    id_dataset = Integer(required=True)
    version_dataset = Integer(required=True)
    dataset = Nested('DatasetSchema', required=True, load_only=True)
