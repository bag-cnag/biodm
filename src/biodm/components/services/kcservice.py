from abc import abstractmethod
from typing import Any, Dict, List, Literal
from pathlib import Path

from biodm.components import Base
from biodm.managers import KeycloakManager
from biodm.tables import Group, User
from biodm.utils.security import UserInfo
from biodm.utils.utils import to_it
from .dbservice import CompositeEntityService


class KCService(CompositeEntityService):
    """Abstract class for local keycloak entities."""
    @property
    def kc(self) -> KeycloakManager:
        """Return KCManager instance."""
        return self.app.kc

    @abstractmethod
    async def read_or_create(self, data: Dict[str, Any], /) -> None:
        """Try to read from DB, create on keycloak side if not present.
           Populate 'id' - Keycloak UUID in string form - in data."""
        raise NotImplementedError


class KCGroupService(KCService):
    async def read_or_create(self, data: Dict[str, Any]) -> None:
        """READ group from keycloak, create if not found.

        :param data: Group data
        :type data: Dict[str, Any]
        """
        path = Path("/" + data['path'].replace("__", "/"))


        group = await self.kc.get_group_by_path(str(path))
        if group:
            data["id"] = group["id"]
            return


        parent_id = None
        if not path.parent.parts == ('/',):
            parent = await self.kc.get_group_by_path(str(path.parent))
            # TODO: better exception
            if not parent:
                raise ValueError("Input path does not match any parent group.")
            parent_id = parent['id']

        data['id'] = await self.kc.create_group(path.name, parent_id)

    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ):
        """Create entities on Keycloak Side before passing to parent class for DB."""
        # Check permissions
        await self._check_permissions("write", user_info, data)
        # Create on keycloak side
        if not stmt_only:
            for group in to_it(data):
                # Group first.
                await self.read_or_create(group)
                # Then Users.
                for user in group.get("users", []):
                    await User.svc.read_or_create(user, [group["path"]], [group["id"]],)
        # DB
        return await super().write(data, stmt_only=stmt_only, **kwargs)

    async def delete(self, pk_val: List[Any], user_info: UserInfo | None = None, **_) -> None:
        """DELETE Group from DB then from Keycloak."""
        group_id = (await self.read(pk_val, fields=['id'])).id
        await super().delete(pk_val, user_info=user_info)
        await self.kc.delete_group(group_id)


class KCUserService(KCService):
    async def read_or_create(
        self,
        data: Dict[str, Any],
        groups: List[str] | None = None,
        group_ids: List[str] | None = None,
    ) -> None:
        """READ entry from Database, CREATE it if not found.

        :param data: Entry object representation
        :type data: Dict[str, Any]
        :param groups: User groups, defaults to None
        :type groups: List[str], optional
        :param group_ids: User groups ids, defaults to None
        :type group_ids: List[str], optional
        :return: User id
        :rtype: str
        """
        user = await self.kc.get_user_by_username(data["username"])
        if user:
            group_ids = group_ids or []
            for gid in group_ids:
                await self.kc.group_user_add(user['id'], gid)
            data['id'] = user['id']
        else:
            data['id'] = await self.kc.create_user(data, groups)
        # Important to remove password as it is not stored locally, SQLA would throw error.
        data.pop('password')

    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ):
        """CREATE entities on Keycloak, before inserting in DB."""
        await self._check_permissions("write", user_info, data)

        if not stmt_only:
            for user in to_it(data):
                # Groups first.
                group_paths, group_ids = [], []
                for group in user.get("groups", []):
                    await Group.svc.read_or_create(group)
                    group_paths.append(group['path'])
                    group_ids.append(group['id'])
                # Then User.
                await self.read_or_create(user, groups=group_paths, group_ids=group_ids)

        return await super().write(data, stmt_only=stmt_only, **kwargs)

    async def delete(self, pk_val: List[Any], user_info: UserInfo | None = None, **_) -> None:
        """DELETE User from DB then from keycloak."""
        user_id = (await self.read(pk_val, fields=['id'])).id
        await super().delete(pk_val, user_info=user_info)
        await self.kc.delete_user(user_id)
