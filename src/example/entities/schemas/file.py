from marshmallow import Schema, validate
from marshmallow.fields import String, List, Nested, Integer, Bool
from biodm.schemas import UploadSchema

class FileSchema(Schema):
    id = Integer()
    filename = String()
    extension = String()
    size = Integer()

    ready = Bool(dump_only=True)
    dl_count = Integer(dump_only=True)
    id_dataset = Integer()
    version_dataset = Integer()

    # submitter_username = String()
    upload = Nested("UploadSchema", dump_only=True)
    # dataset = Nested('DatasetSchema') # , load_only=True
