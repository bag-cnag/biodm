from core.components.controllers import KCController
from core.tables import Group
from core.schemas import GroupSchema

class GroupController(KCController):
    def __init__(self):
        super().__init__(
              entity="Group",
              table=Group,
              schema=GroupSchema)
