from .user import UserSchema
from .group import GroupSchema
from .listgroup import ListGroupSchema

# Headless schemas can be explicitely added to the register.
from marshmallow.class_registry import register
register('ListGroupSchema', ListGroupSchema)
