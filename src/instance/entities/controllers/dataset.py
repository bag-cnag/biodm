from typing import overload

from core.components.controllers import ActiveController
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
    # CRUD operations
    @overload
    def create(**kwargs):
        raise NotImplementedError

    @overload
    def read(**kwargs):
        raise NotImplementedError

    @overload
    def update(**kwargs):
        raise NotImplementedError

    @overload
    def delete(**kwargs):
        raise NotImplementedError
    
    @overload
    def create_update(**kwargs):
        raise NotImplementedError
    
    @overload
    def query(**kwargs):
        raise NotImplementedError
