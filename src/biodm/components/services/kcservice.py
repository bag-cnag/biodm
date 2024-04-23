from abc import abstractmethod
from typing import Any, List

from biodm.components import Base
from biodm.exceptions import FailedRead
from biodm.tables import Group, User
from biodm.utils.utils import to_it
from .dbservice import CompositeEntityService


class KCService(CompositeEntityService):
    @property
    def kc(self):
        """Return KCManager instance."""
        return self.app.kc

    @abstractmethod
    async def _read_or_create(self, **kwargs):
        """Try to read from DB, create on keycloak side if not present. Return id."""
        raise NotImplementedError


class KCGroupService(KCService):
    async def _read_or_create(self, data: dict):
        try:
            return (await self.read(data["name"])).id
        except FailedRead:
            return await self.kc.create_group(data)

    async def create(self, data, stmt_only: bool=False, **kwargs) -> Base | List[Base]:
        """Create entities on Keycloak Side before passing to parent class for DB."""
        # KC
        if not stmt_only:
            for group in to_it(data):
                # Group first.
                group['id'] = await self._read_or_create(group)
                # Then Users.
                for user in group.get("users", []):
                    user['id'] = await User.svc._read_or_create(user,
                                                                [group["name"]], 
                                                                [group['id']])
        # DB
        return await super(KCService, self).create(data, stmt_only=stmt_only, **kwargs)

    async def update(self, pk_val, data: dict, **kwargs) -> Base:
        raise NotImplementedError
        await self.kc.update_group(await self.read(pk_val).id, data)
        return await super(KCService, self).update(id, data, **kwargs)

    async def delete(self, pk_val) -> Any:
        await self.kc.delete_group(await self.read(pk_val).id)
        return await super(KCService, self).delete(pk_val)


class KCUserService(KCService):
    async def _read_or_create(self, data, groups=[], group_ids=[]):
        try:
            user = await self.read(data["username"])
            for gid in group_ids:
                await self.kc.group_user_add(user.id, gid)
            return user.id
        except FailedRead:
            return await self.kc.create_user(data, groups)

    async def create(self, data, stmt_only: bool=False, **kwargs) -> Base | List[Base]:
        """Create entities on Keycloak Side before passing to parent class for DB."""
        # KC
        if not stmt_only:
            for user in to_it(data):
                # Groups first.
                group_names, group_ids = [], []
                for group in user.get("groups", []):
                    group['id'] = await Group.svc._read_or_create(group)
                    group_names.append(group['name'])
                    group_ids.append(group['id'])
                # Then User.
                user['id'] = await self._read_or_create(user, group_names, group_ids)
        # DB
        return await super(KCService, self).create(data, stmt_only=stmt_only, **kwargs)

    async def update(self, pk_val, data: dict, **kwargs) -> Base:
        raise NotImplementedError
        await self.kc.update_user(await self.read(pk_val).id, data)
        return await super(KCService, self).update(pk_val, data, **kwargs)

    async def delete(self, pk_val) -> Any:
        await self.kc.delete_user(await self.read(pk_val).id)
        return await super(KCService, self).delete(pk_val)