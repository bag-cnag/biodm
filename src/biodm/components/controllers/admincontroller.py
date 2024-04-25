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
    def __init__(self, 
                 entity: str = None, 
                 table: Base = None, 
                 schema: Schema = None, 
                 read_public: bool=True):
        if not read_public:
            self.read = admin_required(self.create)
            self.query = admin_required(self.query)

        super().__init__(entity, table, schema)

    @admin_required
    async def create(self, *args, **kwargs):
        return super().create(*args, **kwargs)

    async def read(self, *args, **kwargs):
        return super().read(*args, **kwargs)

    @admin_required
    async def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)

    @admin_required
    async def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)
    
    @admin_required
    async def create_update(self, *args, **kwargs):
        return super().create_update(*args, **kwargs)
    
    async def query(self, *args, **kwargs):
        return super().query(*args, **kwargs)
