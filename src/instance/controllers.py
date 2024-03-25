from core.components import ActiveController, S3Controller

from .entities.tables import (Dataset, File, Group, User, Tag)
from .entities.schemas import (
    TagSchema, FileSchema, GroupSchema, UserSchema, DatasetSchema
)


class DatasetController(ActiveController):
    def __init__(self):
        super().__init__(
            table=Dataset,
            schema=DatasetSchema)


class FileController(S3Controller):
    def __init__(self):
        super().__init__(
            table=File,
            schema=FileSchema)


class GroupController(ActiveController):
    def __init__(self):
        super().__init__(
            table=Group,
            schema=GroupSchema)


class TagController(ActiveController):
    def __init__(self):
        super().__init__(
            table=Tag,
            schema=TagSchema)


class UserController(ActiveController):
    def __init__(self):
        super().__init__(
            table=User,
            schema=UserSchema)


CONTROLLERS = [DatasetController, FileController, GroupController, 
               TagController, UserController]
