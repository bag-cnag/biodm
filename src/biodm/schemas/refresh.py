# from marshmallow import Schema
from marshmallow.fields import String

from biodm.components import Schema


class RefreshSchema(Schema):
    """Schema for logout"""
    refresh_token = String(required=True)
