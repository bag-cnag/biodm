from typing import List, Dict, Any

from biodm.components import Base
from biodm.utils.security import UserInfo
from .dbservice import CompositeEntityService


class K8Service(CompositeEntityService):
    """Manages kubernetes instances.
    """
    @property
    def k8s(self):
        return self.app.k8s

    async def create(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Base | List[Base] | str:
        """Submits manifest to kubernetes cluster before inserting into DB."""
        # K8s
        if not stmt_only:
            pass
            # data = {

            # }
        # DB
        return await super().create(data, stmt_only=stmt_only, **kwargs)
