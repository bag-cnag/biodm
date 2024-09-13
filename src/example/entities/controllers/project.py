from biodm.components.controllers import ResourceController, overload_docstring
from biodm.utils.security import admin_required, login_required


class ProjectController(ResourceController):
    # @admin_required
    @overload_docstring
    async def create(**kwargs):
        """

        ---

        description: Create Project from request body.
        requestBody:
            description: payload.
            required: true
            content:
                application/json:
                    schema: ProjectSchema
        responses:
            201:
                description: Project Created
                examples: |
                    {"name": "pr_test_xyz"}
                content:
                    application/json:
                        schema: ProjectSchema
            204:
                description: Empty Payload.
        """
