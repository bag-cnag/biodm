from marshmallow import Schema
from marshmallow.fields import String, List, Nested, Integer

from biodm.utils.utils import check_hash

class PartsEtagSchema(Schema):
    PartNumber = Integer()
    ETag = String(validate=check_hash)

class UploadPartSchema(Schema):
    upload_id = Integer()
    part_number = Integer()
    form = String()

class UploadSchema(Schema):
    id = Integer()
    parts = List(Nested('UploadPartSchema'))
