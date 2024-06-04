from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, Bool


class FileSchema(Schema):
    id = Integer()
    filename = String(required=True)
    extension = String(required=True)
    upload_form = String(required=False, dump_only=True)
    ready = Bool(required=False, dump_only=True)
    id_dataset = Integer(required=True)
    version_dataset = Integer(required=True)
    # dataset = Nested('DatasetSchema', required=True) # , load_only=True
