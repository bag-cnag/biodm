"""Internally managed schemas."""
from marshmallow.class_registry import register

from .user import UserSchema
from .group import GroupSchema
from .listgroup import ListGroupSchema
from .upload import UploadSchema, PartsEtagSchema

""" Headless schemas should be explicitely added to the register. """
register('ListGroupSchema', ListGroupSchema)
