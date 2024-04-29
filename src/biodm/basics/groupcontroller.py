from biodm.components.controllers import KCController
from biodm.tables import Group
from biodm.schemas import GroupSchema


class GroupController(KCController):
    """"""
    def __init__(self, app):
        super().__init__(app=app, entity="Group", table=Group, schema=GroupSchema)
