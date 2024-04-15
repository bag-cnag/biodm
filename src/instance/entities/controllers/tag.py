from core.components.controllers import ActiveController, overload_docstring


class TagController(ActiveController):
    @overload_docstring
    async def create(**kwargs):
        """
        responses:
          201:
              description: Create Tag.
              examples: |
                {"name": "epidemiology"}
          204:
              description: Empty Payload    
        """

    @overload_docstring
    async def read(**kwargs):
        """
        responses:
          200:
            description: Found matching Tag.
            examples: |
              {"name": "epidemiology"} 
          404:
            description: Tag not found.
        """
