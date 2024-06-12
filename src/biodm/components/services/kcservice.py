from abc import abstractmethod
from typing import Any, Dict, List

from biodm.components import Base
from biodm.exceptions import FailedRead
from biodm.tables import Group, User, user
from biodm.utils.security import UserInfo
from biodm.utils.utils import to_it
from .dbservice import CompositeEntityService


class KCService(CompositeEntityService):
    """Abstract class for local keycloak entities."""
    @property
    def kc(self):
        """Return KCManager instance."""
        return self.app.kc

    @abstractmethod
    async def read_or_create(self, *args, **kwargs) -> str:
        """Try to read from DB, create on keycloak side if not present.
           Return id: UUID in string form."""
        raise NotImplementedError


class KCGroupService(KCService):
    async def read_or_create(self, data: Dict[str, Any], user_info: UserInfo = None) -> str:
        """READ entry from Database, CREATE it if not found.

        :param data: Entry object representation
        :type data: Dict[str, Any]
        :return: Group id
        :rtype: str
        """
        try:
            return (await self.read(data["name"], fields=['id'], user_info=user_info)).id
        except FailedRead:
            return await self.kc.create_group(data)

    async def create(
        self,
        data,
        stmt_only: bool = False,
        user_info: UserInfo = None,
        **kwargs
    ) -> Base | List[Base]:
        """Create entities on Keycloak Side before passing to parent class for DB."""
        # KC
        if not stmt_only:
            for group in to_it(data):
                # Group first.
                group['id'] = await self.read_or_create(group, user_info)
                # Then Users.
                for user in group.get("users", []):
                    user['id'] = await User.svc.read_or_create(
                        user,
                        [group["name"]],
                        [group['id']],
                        user_info=user_info
                    )
        # DB
        return await super().create(data, stmt_only=stmt_only, user_info=user_info, **kwargs)

    async def delete(self, pk_val, user_info: UserInfo = None) -> Any:
        """DELETE Group on Keycloak before deleting DB entry."""
        await self.kc.delete_group(await self.read(pk_val).id)
        return await super().delete(pk_val, user_info=user_info)


class KCUserService(KCService):
    async def read_or_create(
        self,
        data: Dict[str, Any],
        groups: List[str] = None,
        group_ids: List[str]=None,
        user_info: UserInfo=None,
    ) -> str:
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
        try:
            user_id = (await self.read(data["username"], fields=['id'], user_info=user_info)).id
            group_ids = group_ids or []
            for gid in group_ids:
                await self.kc.group_user_add(user_id, gid)
            return user_id
        except FailedRead:
            id = await self.kc.create_user(data, groups)
            # Take out password from user dict, as it is not stored locally.
            data.pop('password')
            return id

    async def create(self, data, stmt_only: bool = False, user_info: UserInfo=None, **kwargs) -> Base | List[Base]:
        """CREATE entities on Keycloak, before inserting in DB."""
        # KC
        if not stmt_only:
            for user in to_it(data):
                # Groups first.
                group_names, group_ids = [], []
                for group in user.get("groups", []):
                    group['id'] = await Group.svc.read_or_create(group, user_info=user_info)
                    group_names.append(group['name'])
                    group_ids.append(group['id'])
                # Then User.
                user['id'] = await self.read_or_create(user, group_names, group_ids, user_info=user_info)
        # DB
        return await super().create(data, stmt_only=stmt_only, user_info=user_info, **kwargs)

    async def delete(self, pk_val, user_info: UserInfo) -> Any:
        """DELETE User on Keycloak before deleting DB entry."""
        await self.kc.delete_user(await self.read(pk_val).id)
        return await super().delete(pk_val, user_info=user_info)
