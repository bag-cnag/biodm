from abc import ABCMeta, abstractmethod
from typing import Dict, Type

from biodm.component import ApiComponent
from sqlalchemy.ext.asyncio import AsyncSession

from .table import Base


class K8sManifest(ApiComponent, metaclass=ABCMeta):
    """Generic class holding a Kubernetes manifest linked with a Table.

    To use in place of a Controller as K8s related routes are not really meant to be public.
    All Manifests are processed and exposed under K8sController.
    """
    table: Type[Base]
    namespace: str = "default"

    def __init__(self, app) -> None:
        super().__init__(app)
        from biodm.components.services import K8Service
        self.svc = K8Service(app=app, table=self.table, manifest=self)

    @abstractmethod
    async def gen_manifest(
        self,
        db_obj: Base,
        session: AsyncSession,
        **kwargs
    ) -> Dict[str, str]:
        """Returns a generated manifest."""
        raise NotImplementedError
