from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, Bool


class FileSchema(Schema):
    id = Integer()
    filename = String()
    extension = String()
    upload_form = String(dump_only=True)
    ready = Bool(dump_only=True)
    dl_count = Integer(dump_only=True)
    id_dataset = Integer()
    version_dataset = Integer()
    # dataset = Nested('DatasetSchema') # , load_only=True
