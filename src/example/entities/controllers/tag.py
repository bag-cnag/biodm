from biodm.components.controllers import ResourceController, overload_docstring
from biodm.utils.security import login_required


class TagController(ResourceController):
    @login_required
    @overload_docstring
    async def create(**kwargs):
        """
        requestBody:
          description: payload.
          required: true
          content:
              application/json:
                  schema: TagSchema
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

    @login_required
    @overload_docstring
    async def read(**kwargs):
        """
        parameters:
          - in: path
            name: name
            description: Tag name
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
