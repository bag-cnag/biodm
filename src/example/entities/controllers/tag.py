from biodm.components.controllers import ResourceController, overload_docstring


class TagController(ResourceController):
    @overload_docstring
    async def create(**kwargs):
        """
        responses:
          201:
              description: Create Tag.
              examples: |
                {"name": "epidemiology"}
              content:
                application/json:
                  schema: TagSchema
          204:
              description: Empty Payload    
        """

    @overload_docstring
    async def read(**kwargs):
        """
        parameters:
          - in: path
            name: id
            description: entity id
        responses:
          200:
            description: Found matching Tag.
            examples: |
              {"name": "epidemiology"}
          content:
            application/json:
              schema: TagSchema
          404:
            description: Tag not found.
        """
