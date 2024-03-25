from core.components import ActiveController, S3Controller

from .entities.tables import (Dataset, File, Group, User, Tag)
from .entities.schemas import (
    TagSchema, FileSchema, GroupSchema, UserSchema, DatasetSchema
)

# E.g. on how to overload inferred tables/schemas names:
#    # class D4ta5setController(ActiveController):
#    #    # def __init__(self):
#    #    #     super().__init__(
#    #    #         entity="Dataset"
#    #    #         table=Dataset,
#    #    #         schema=DatasetSchema)


class DatasetController(ActiveController):
    pass


class FileController(S3Controller):
    pass


class GroupController(ActiveController):
    pass


class TagController(ActiveController):
    pass


class UserController(ActiveController):
    pass


CONTROLLERS = [DatasetController, FileController, GroupController, 
               TagController, UserController]
