from biodm.components.controllers import ResourceController
from biodm.tables import Group
from biodm.schemas import GroupSchema


class GroupController(ResourceController):
    """Group Controller."""
    def __init__(self, app):
        super().__init__(app=app, entity="Group", table=Group, schema=GroupSchema)
