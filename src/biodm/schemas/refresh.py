from marshmallow import Schema
from marshmallow.fields import String


class RefreshSchema(Schema):
    """Schema for logout"""
    refresh_token = String(required=True)
