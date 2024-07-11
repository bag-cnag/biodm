from biodm.components.controllers import ResourceController, overload_docstring
from biodm.utils.security import admin_required


class ProjectController(ResourceController):
    # @admin_required
    @overload_docstring
    async def create(**kwargs):
        """
        description: Create new Project from request body.
        responses:
            201:
                description: Create Project.
                examples: |
                    {"name": "pr_test_xyz"}
                content:
                  application/json:
                    schema: ProjectSchema
            204:
                description: Empty Payload
        """
