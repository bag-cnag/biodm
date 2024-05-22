from biodm.components.controllers import ResourceController, overload_docstring
from biodm.utils.security import admin_required


class ProjectController(ResourceController):
    @admin_required
    @overload_docstring
    async def create(**kwargs):
        """
        responses:
          201:
              description: Create Project.
              examples: |
                {"name": "pr_test_xyz"}
          204:
              description: Empty Payload.
        """

    @admin_required
    @overload_docstring
    async def update(**kwargs):
        """abc"""

    @admin_required
    @overload_docstring
    async def delete(**kwargs):
        """abc"""
