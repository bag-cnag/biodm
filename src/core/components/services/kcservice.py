from typing import List, Any

from core.components import Base
from .dbservice import UnaryEntityService
from instance import config


class KCService(UnaryEntityService):
    pass


class KCUserService(KCService):
    """Service that manage Keycloak Users."""
    async def create(self, data, stmt_only: bool=False) -> Base | List[Base]:
        """On CREATE, foward to keycloak."""
        # await self.app.kc.create_user(data)
        return await super().create(data, stmt_only)

    async def update(self, id, data: dict) -> Base:
        """On UPDATE, forward to keycloak."""
        # await self.app.kc.update_user(id, data)
        return await super().update(id, data)

    async def delete(self, id) -> Any:
        """On DELETE, forward to keycloak."""
        # await self.app.kc.delete_user(id)
        return await super().delete(id)


class KCGroupService(KCService):
    """Service that manage Keycloak Groups."""
    async def create(self, data, stmt_only: bool=False) -> Base | List[Base]:
        """On CREATE, foward to keycloak."""
        # await self.app.kc.create_group(data)
        return await super().create(data, stmt_only)

    async def update(self, id, data: dict) -> Base:
        """On UPDATE, forward to keycloak."""
        # await self.app.kc.update_group(id, data)
        return await super().update(id, data)

    async def delete(self, id) -> Any:
        """On DELETE, forward to keycloak."""
        # await self.app.kc.delete_group(id)
        return await super().delete(id)
