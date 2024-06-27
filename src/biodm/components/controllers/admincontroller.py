from marshmallow import Schema

from biodm.components import Base
from biodm.utils.security import admin_required, login_required
from .resourcecontroller import ResourceController


class AdminController(ResourceController):
    """Class for admin managed entities, i.e. KC User/Groups/Projects.

    CRUD Behaviour:
        - READ require an admin token based on read_public flag
        - CREATE/UPDATE/DELETE require an admin token
    """
    def __init__(self, *args, read_public=True, **kwargs) -> None:
        self.create = admin_required(self.create)
        self.update = admin_required(self.update)
        self.delete = admin_required(self.delete)

        if not read_public:
            self.read = login_required(self.read)
            self.filter = login_required(self.filter)

        super().__init__(*args, **kwargs)
