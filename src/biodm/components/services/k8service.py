from typing import List

from biodm.components import Base
from .dbservice import CompositeEntityService


class K8Service(CompositeEntityService):
    """Manages kubernetes instances.
    """
    @property
    def k8s(self):
        return self.app.k8s

    async def create(self, data, stmt_only: bool=False, **kwargs) -> Base | List[Base]:
        """Submits manifest to kubernetes cluster before inserting into DB."""
        # K8s
        if not stmt_only:
            pass
            # data = {

            # }
        # DB
        return await super().create(data, stmt_only=stmt_only, **kwargs)