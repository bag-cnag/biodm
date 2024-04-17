from core.components.controllers import ResourceController, overload_docstring

# E.g. on how to overload inferred tables/schemas names:
# from .entities.tables import Dataset
# from .entities.schemas import DatasetSchema
# class D4ta5setController(ResourceController):
#     def __init__(self):
#         super().__init__(
#               entity="Dataset"
#               table=Dataset,
#               schema=DatasetSchema)


class DatasetController(ResourceController):
    @overload_docstring
    async def create(**kwargs):
        """
        responses:
          201:
              description: Create Dataset.
              examples: |
                # TODO:
                {"name": "instant_sc_1234", ""}
          204:
              description: Empty Payload.
        """

    @overload_docstring
    async def read(**kwargs):
        """
        parameters:
          - in: path
            id: entity id
        responses:
          200:
            description: Found matching Dataset.
            examples: |
              # TODO:
              {"name": "epidemiology"} 
          404:
            description: Dataset not found.
        """

