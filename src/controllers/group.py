from controllers import UnaryEntityController
from controllers.schemas import GroupSchema
from model.services import GroupService
from model.tables import Group


class GroupController(UnaryEntityController):
    def __init__(self):
        super().__init__(
            svc=GroupService,
            table=Group,
            schema=GroupSchema)
