from abc import abstractmethod
from typing import Any, Dict, List
from pathlib import Path

from biodm.exceptions import DataError, UnauthorizedError
from biodm.managers import KeycloakManager
from biodm.tables import Group, User
from biodm.utils.security import UserInfo
from biodm.utils.utils import to_it, classproperty
from .dbservice import CompositeEntityService


class KCService(CompositeEntityService):
    """Abstract class for local keycloak entities."""
    @classproperty
    def kc(cls) -> KeycloakManager:
        """Return KCManager instance."""
        return cls.app.kc

    @abstractmethod
    async def _update(self, remote_id: str, data: Dict[str, Any]):
        """Keycloak entity update method."""
        raise NotImplementedError

    async def sync(
        self,
        remote: Dict[str, Any],
        data: Dict[str, Any],
        user_info: UserInfo
    ):
        """Sync Keycloak and input data."""
        inter = remote.keys() & (set(c.name for c in self.table.__table__.columns) - self.table.pk)
        fill = {
            key: remote[key] for key in inter if key not in data.keys()
        }
        update = {
            key: data[key] for key in inter
            if data.get(key, None) and data.get(key, None) != remote.get(key, None)
        }
        if update:
            if not user_info.is_admin:
                raise UnauthorizedError(
                    f"only administrators are allowed to update keycloak entities."
                )
            await self._update(remote['id'], update)
        data.update(fill)

    @abstractmethod
    async def read_or_create(
        self,
        data: Dict[str, Any],
        user_info: UserInfo,
        /
    ) -> None:
        """Query entity from keycloak, create it in case it does not exists, update in case it does.
        Populates data with resulting id and/or found information."""
        raise NotImplementedError


class KCGroupService(KCService):
    @staticmethod
    def kcpath(path) -> Path:
        """Compute keycloak path from api path."""
        return Path("/" + path.replace("__", "/"))

    async def _update(self, remote_id: str, data: Dict[str, Any]):
        return await self.kc.update_group(group_id=remote_id, data=data)

    async def read_or_create(
        self,
        data: Dict[str, Any],
        user_info: UserInfo
    ) -> None:
        """READ group from keycloak, CREATE if missing, UPDATE if exists.

        :param data: Group data
        :type data: Dict[str, Any]
        :param user_info: requesting user info
        :type user_info: UserInfo
        """
        path = self.kcpath(data['path'])
        group = await self.kc.get_group_by_path(str(path))

        if group:
            await self.sync(group, data, user_info=user_info)
            return

        if not user_info.is_admin:
            raise UnauthorizedError(
                f"group {path} does not exists, only administrators are allowed to create new ones."
            )

        parent_id = None
        if not path.parent.parts == ('/',):
            parent = await self.kc.get_group_by_path(str(path.parent))
            if not parent:
                raise DataError("Input path does not match any parent group.")
            parent_id = parent['id']

        data['id'] = await self.kc.create_group(path.name, parent_id)

    async def write(
        self,
        data: List[Dict[str, Any]] | Dict[str, Any],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ):
        """Create entities on Keycloak Side before passing to parent class for DB."""
        # Create on keycloak side
        for group in to_it(data):
            # Group first.
            await self.read_or_create(group, user_info=user_info)
            # Then Users.
            for user in group.get("users", []):
                await User.svc.read_or_create(
                    user,
                    user_info=user_info,
                    groups=[group["path"]],
                    group_ids=[group["id"]]
                )

        # Send to DB without user_info.
        return await super().write(data, stmt_only=stmt_only, **kwargs)

    async def delete(self, pk_val: List[Any], user_info: UserInfo | None = None, **_) -> None:
        """DELETE Group from DB then from Keycloak."""
        group_id = (await self.read(pk_val, fields=['id'])).id
        await super().delete(pk_val, user_info=user_info)
        await self.kc.delete_group(group_id)


class KCUserService(KCService):
    async def _update(self, remote_id: str, data: Dict[str, Any]):
        return await self.kc.update_user(user_id=remote_id, data=data)

    async def read_or_create(
        self,
        data: Dict[str, Any],
        user_info: UserInfo,
        groups: List[str] | None = None,
        group_ids: List[str] | None = None,
    ) -> None:
        """READ User from keycloak, CREATE if missing, UPDATE if exists.

        :param data: Entry object representation
        :type data: Dict[str, Any]
        :param user_info: requesting user info
        :type user_info: UserInfo
        :param groups: User groups names, defaults to None
        :type groups: List[str], optional
        :param group_ids: User groups ids, defaults to None
        :type group_ids: List[str], optional
        :return: User id
        :rtype: str
        """
        user = await self.kc.get_user_by_username(data["username"])
        groups = [str(KCGroupService.kcpath(group)) for group in groups]
        if user:
            # TODO: manage groups ? Maybe useless.
            group_ids = group_ids or []
            for gid in group_ids:
                await self.kc.group_user_add(user['id'], gid)
            await self.sync(user, data, user_info=user_info)

        elif not user_info.is_admin:
            raise UnauthorizedError(
                f"user {data['username']} does not exists, "
                "only administrators are allowed to create new ones."
            )

        elif not data.get('password', None):
            raise DataError("Missing password in order to create User.")

        else:
            data['id'] = await self.kc.create_user(data, groups)

        # Important to remove password as it is not stored locally, SQLA would throw error.
        data.pop('password', None)

    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ):
        """CREATE entities on Keycloak, before inserting in DB."""
        for user in to_it(data):
            # Groups first.
            group_paths, group_ids = [], []
            for group in user.get("groups", []):
                await Group.svc.read_or_create(
                    group,
                    user_info=user_info,
                )
                group_paths.append(group['path'])
                group_ids.append(group['id'])
            # Then User.
            await self.read_or_create(
                user,
                user_info=user_info,
                groups=group_paths,
                group_ids=group_ids
            )

        return await super().write(data, stmt_only=stmt_only, **kwargs)

    async def delete(self, pk_val: List[Any], user_info: UserInfo | None = None, **_) -> None:
        """DELETE User from DB then from keycloak."""
        user_id = (await self.read(pk_val, fields=['id'])).id
        await super().delete(pk_val, user_info=user_info)
        await self.kc.delete_user(user_id)
