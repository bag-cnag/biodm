from biodm.components.controllers import KCController
from biodm.tables import Group
from biodm.schemas import GroupSchema

class GroupController(KCController):
    def __init__(self):
        super().__init__(
              entity="Group",
              table=Group,
              schema=GroupSchema)
