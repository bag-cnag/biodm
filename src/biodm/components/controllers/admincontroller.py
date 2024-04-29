from marshmallow import Schema

from biodm.components import Base
from biodm.utils.security import admin_required
from .resourcecontroller import ResourceController


class AdminController(ResourceController):
    """Class for admin managed entities, i.e. KC User/Groups/Projects.
    
    CRUD Behaviour:
        - READ require an admin token based on read_public flag 
        - CREATE/UPDATE/DELETE require an admin token 
    """
    def __init__(
        self,
        entity: str = None,
        table: Base = None,
        schema: Schema = None,
        read_public: bool = True,
    ):
        self.create = admin_required(self.create)
        self.update = admin_required(self.update)
        self.delete = admin_required(self.delete)
        self.create_update = admin_required(self.create_update)

        if not read_public:
            self.read = admin_required(self.create)
            self.filter = admin_required(self.filter)


        super().__init__(entity, table, schema)
