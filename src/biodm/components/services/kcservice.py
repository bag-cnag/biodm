from abc import abstractmethod
from typing import Any, Dict, List
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from biodm.components import Base
from biodm.exceptions import DataError, UnauthorizedError
from biodm.managers import KeycloakManager, DatabaseManager
from biodm.tables import Group, User
from biodm.utils.security import UserInfo
from biodm.utils.sqla import UpsertStmtValuesHolder
from biodm.utils.utils import to_it, classproperty
from .dbservice import CompositeEntityService


class KCService(CompositeEntityService):
    """Abstract class for local keycloak entities."""
    @classproperty
    def kc(cls) -> KeycloakManager:
        """Return KCManager instance."""
        return cls.app.kc

    @DatabaseManager.in_session
    async def _insert(
        self,
        stmt: UpsertStmtValuesHolder,
        user_info: UserInfo | None,
        session: AsyncSession
    ) -> Base:
        """INSERT one object into the DB, check token write permissions before commit."""
        try:
            return await super()._insert(stmt, user_info=user_info, session=session)
        except DataError as de:
            if "missing the following: {'id'}." in de.detail:
                raise UnauthorizedError(
                    "Missing keykloak privileges to create an entity "
                    "that does not exist locally"
                )

    @abstractmethod
    async def _update(self, remote_id: str, data: Dict[str, Any], user_info: UserInfo):
        """Keycloak entity update method."""
        raise NotImplementedError

    @abstractmethod
    async def sync_all(self, user_info: UserInfo) -> None:
        """Import all entities of that type from keycloak."""
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
            await self._update(remote['id'], update, user_info=user_info)
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

    @staticmethod
    def dbpath(path) -> str:
        """Compute api path from keycloak path"""
        return path[1:].replace('/', '__')

    async def sync_all(self, user_info: UserInfo) -> None:
        def parse_one(one):
            entry = { # extract
                "id": one['id'],
                "path": self.dbpath(one['path']),
            }
            children = []

            for sub in to_it(one['subGroups']): # recurse
                children.append(parse_one(sub))

            if children:
                entry["children"] = children

            return entry

        groups = await self.kc.get_groups(user_info=user_info)

        data = []
        for one in to_it(groups):
            data.append(parse_one(one))

        return await super().write(data, stmt_only=False, user_info=user_info)

    async def _update(self, remote_id: str, data: Dict[str, Any], user_info: UserInfo):
        return await self.kc.update_group(group_id=remote_id, data=data, user_info=user_info)

    async def read_or_create(
        self,
        data: Dict[str, Any],
        user_info: UserInfo
    ) -> None:
        """READ group from keycloak, CREATE if missing, UPDATE if exists.

        For regular users with no read permissions on groups, this method will result in a
        dictionary with no 'id' field, which is required when keycloak is enabled.
        Ultimately leading the insert statement

        :param data: Group data
        :type data: Dict[str, Any]
        :param user_info: requesting user info
        :type user_info: UserInfo
        """
        path = self.kcpath(data['path'])
        group = await self.kc.get_group_by_path(str(path), user_info=user_info)

        if group:
            await self.sync(group, data, user_info=user_info)
            return

        parent_id = None
        failed_parent = False
        if not path.parent.parts == ('/',):
            parent = await self.kc.get_group_by_path(str(path.parent), user_info=user_info)
            if parent:
                parent_id = parent['id']
            else:
                failed_parent = True

        cr_id = await self.kc.create_group(path.name, parent_id, user_info=user_info)
        if cr_id:
            data['id'] = cr_id
            if failed_parent:
                # Had right to see/create group but not parent, it means parent only failed.
                raise DataError("Input path does not match any parent group.")

    async def write(
        self,
        data: List[Dict[str, Any]] | Dict[str, Any],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ):
        """Create entities on Keycloak Side before passing to parent class for DB."""
        # Create on keycloak side
        if user_info and user_info.keycloak_admin:
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

        return await super().write(data, stmt_only=stmt_only, user_info=user_info, **kwargs)

    async def delete(self, pk_val: List[Any], user_info: UserInfo | None = None, **_) -> None:
        """DELETE Group from DB then from Keycloak."""
        group_id = (await self.read(pk_val, fields=['id'])).id
        await super().delete(pk_val, user_info=user_info)
        await self.kc.delete_group(group_id, user_info=user_info)


class KCUserService(KCService):
    async def sync_all(self, user_info: UserInfo) -> None:
        """Import all entities of that type from keycloak.
        Assumes that the equivalent method of KCGroupService has been called prior.
        """
        users = await self.kc.get_users(user_info=user_info)

        data = []
        for one in to_it(users):
            groups = await self.kc.get_user_groups(one['id'], user_info=user_info)

            user = {
                "id": one["id"],
                "username": one["username"]
            }
            for prop in ("firstName", "lastName", "email"):
                if hasattr(one, prop):
                    user[prop] = one[prop]

            groups_prop = []
            for group in groups:
                groups_prop.append({"path": KCGroupService.dbpath(group['path'])})

            if groups_prop:
                user["groups"] = groups_prop

            data.append(user)
        await super().write(data, stmt_only=False, user_info=user_info)

    async def _update(self, remote_id: str, data: Dict[str, Any], user_info: UserInfo):
        return await self.kc.update_user(user_id=remote_id, data=data, user_info=user_info)

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
        :param groups: User groups names, defaults to None
        :type groups: List[str], optional
        :param group_ids: User groups ids, defaults to None
        :type group_ids: List[str], optional
        :return: User id
        :rtype: str
        """
        user = await self.kc.get_user_by_username(data["username"], user_info=user_info)
        groups = [str(KCGroupService.kcpath(group)) for group in groups]
        if user:
            # TODO: manage groups ? Maybe useless.
            group_ids = group_ids or []
            for gid in group_ids:
                await self.kc.group_user_add(user['id'], gid, user_info=user_info)
            await self.sync(user, data, user_info=user_info)

        else:
            cr_id = await self.kc.create_user(data, groups, user_info=user_info)
            if cr_id:
                data['id'] = cr_id

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
        if user_info and user_info.keycloak_admin:
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

        return await super().write(data, stmt_only=stmt_only, user_info=user_info, **kwargs)

    async def delete(self, pk_val: List[Any], user_info: UserInfo | None = None, **_) -> None:
        """DELETE User from DB then from keycloak."""
        user_id = (await self.read(pk_val, fields=['id'])).id
        await super().delete(pk_val, user_info=user_info)
        await self.kc.delete_user(user_id, user_info=user_info)
