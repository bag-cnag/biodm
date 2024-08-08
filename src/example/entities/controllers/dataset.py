from biodm.components.controllers import ResourceController, overload_docstring

# E.g. on how to overload inferred tables/schemas names:
# from .entities.tables import Dataset
# from .entities.schemas import DatasetSchema
# class D4ta5setController(ResourceController):
#     def __init__(self) -> None:
#         super().__init__(
#               entity="Dataset"
#               table=Dataset,
#               schema=DatasetSchema)


class DatasetController(ResourceController):
    @overload_docstring
    async def create(**kwargs):
        """
        requestBody:
            description: payload.
            required: true
            content:
                application/json:
                    schema: DatasetSchema
        responses:
            201:
                description: Create Dataset.
                content:
                    application/json:
                        schema: DatasetSchema
            204:
                description: Empty Payload.
        """

    @overload_docstring
    async def read(**kwargs):
        """
        parameters:
            - in: path
              name: id
              description: Dataset id
            - in: path
              name: version
              description: Dataset version
        responses:
            200:
                description: Found matching Dataset.
                examples: |
                    {"id": "1", "version": "1", "name": "instant_sc_1234"}
                content:
                    application/json:
                        schema: DatasetSchema
            404:
                description: Dataset not found.
        """
