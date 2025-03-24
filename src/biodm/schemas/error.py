from marshmallow import Schema
from marshmallow.fields import String, Integer


class ErrorSchema(Schema):
    """Schema for errors returned by Api, mostly for apispec purposes."""
    code = Integer(required=True)
    reason = String(required=True)
    message = String(required=True)
