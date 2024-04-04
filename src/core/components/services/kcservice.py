from typing import List, Any, Tuple

from core.components import Base
from core.exceptions import ImplementionErrror
from .dbservice import CompositeEntityService


class KCService(CompositeEntityService):
    def __init__(self, app, table: Base, pk: Tuple[str], *args, **kwargs) -> None:
        super().__init__(app, table, pk, *args, **kwargs)
        self._set_kc_methods()

    def _set_kc_methods(self):
        """Sets _kc_{create, update, delete}, according to current entity."""
        ent = self.table.__name__.lower()
        if ent not in ("user", "group"):
            raise ImplementionErrror("KCService, only supports Users/Groups at the moment.")
        for v in ("create", "update", "delete"):
            self.__setattr__(f"_kc_{v}", self.app.kc.__getattribute__(f"{v}_{ent}"))

    async def create(self, data, stmt_only: bool=False) -> Base | List[Base]:
        """On CREATE, foward to keycloak."""
        id = await self._kc_create(data)
        data["id"] = id
        return await super().create(data, stmt_only)

    async def update(self, id, data: dict) -> Base:
        """On UPDATE, forward to keycloak."""
        await self._kc_update(id, data)
        return await super().update(id, data)

    async def delete(self, id) -> Any:
        """On DELETE, forward to keycloak."""
        item = await self.read(id)
        await self._kc_delete(item.id)
        return await super().delete(id)
