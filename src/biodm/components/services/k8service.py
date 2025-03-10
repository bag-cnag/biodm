from typing import Any, Callable, Sequence

from sqlalchemy import Insert
from sqlalchemy.ext.asyncio import AsyncSession
from kubernetes.client.exceptions import ApiException

from biodm.components import Base, K8sManifest
from biodm.exceptions import ImplementionError
from biodm.managers import DatabaseManager, K8sManager
from biodm.utils.security import UserInfo
from biodm.utils.utils import classproperty
from .dbservice import CompositeEntityService


class K8Service(CompositeEntityService):
    """Manage kubernetes instances associated to one manifest."""
    manifest: K8sManifest

    def __init__(self, app, table: Base, manifest: K8sManifest, *args, **kwargs) -> None:
        self.manifest = manifest
        super().__init__(app, table, *args, **kwargs)

    @classproperty
    def k8(cls) -> K8sManager:
        return cls.app.k8

    async def _gen_and_submit_manifest(self, db_obj: Base, session: AsyncSession) -> None:
        manifest = await self.manifest.gen_manifest(db_obj, session)

        # Set instance name.
        instance_name = manifest.get("metadata", {}).get("name", None)
        await db_obj.awaitable_attrs.name
        setattr(db_obj, 'name', instance_name)

        # Ensure submitting happens in the proper namespace.
        self.k8.change_namespace(self.manifest.namespace)

        if hasattr(self.manifest, 'submit_manifest'):
            self.manifest.submit_manifest(manifest)
        else:
            try:
                f: Callable
                match manifest.get('kind', manifest.get('Kind')).lower():
                    case 'deployment':
                        f = self.k8.create_deployment
                    case 'ingress':
                        f = self.k8.create_ingress
                    case 'service':
                        f = self.k8.create_service
                    case _:
                        f = self.k8.create_custom_resource
                f(manifest)
            except ApiException as e:
                raise ImplementionError(
                    "Default manifest submission modes failed. Error: " + str(e) +
                    "Consider implementing a 'submit_manifest' method on your own."
                )

    @DatabaseManager.in_session
    async def _insert(
        self,
        stmt: Insert,
        user_info: UserInfo | None,
        session: AsyncSession
    ) -> (Any | None):
        """INSERT special case for file: populate url after getting entity id."""
        k8sinst = await super()._insert(stmt, user_info=user_info, session=session)
        await self._gen_and_submit_manifest(k8sinst, session=session)
        return k8sinst

    @DatabaseManager.in_session
    async def _insert_list(
        self,
        stmts: Sequence[Insert],
        user_info: UserInfo | None,
        session: AsyncSession
    ) -> Sequence[Base]:
        """INSERT many objects into the DB database, check token write permission before commit."""
        k8sinsts = await super()._insert_list(stmts, user_info=user_info, session=session)
        for k8sinst in k8sinsts:
            await self._gen_and_submit_manifest(k8sinst, session=session)
        return k8sinsts
