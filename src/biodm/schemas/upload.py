from marshmallow import Schema #, validate
from marshmallow.fields import String, List, Nested, Integer

class PartsEtagSchema(Schema):
    PartNumber = Integer()
    ETag = String()

class UploadPartSchema(Schema):
    id_upload = Integer()
    part_number = Integer()
    form = String()

class UploadSchema(Schema):
    id = Integer()
    parts = List(Nested('UploadPartSchema'))
