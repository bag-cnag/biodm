# from marshmallow import Schema
from marshmallow.fields import String, Number

from biodm.components import Schema


class ErrorSchema(Schema):
    """Schema for errors returned by Api, mostly for apispec purposes."""
    code = Number(required=True)
    reason = String(required=True)
    message = String(required=True)
