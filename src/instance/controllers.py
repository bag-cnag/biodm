from core.components.controllers import ActiveController, S3Controller


# E.g. on how to overload inferred tables/schemas names:
# from .entities.tables import Dataset
# from .entities.schemas import DatasetSchema
# class D4ta5setController(ActiveController):
#     def __init__(self):
#         super().__init__(
#               entity="Dataset"
#               table=Dataset,
#               schema=DatasetSchema)


class DatasetController(ActiveController):
    pass


class TagController(ActiveController):
    pass


class FileController(S3Controller):
    pass


CONTROLLERS = [DatasetController, FileController, TagController]
