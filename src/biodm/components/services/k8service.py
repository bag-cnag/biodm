from typing import List, Dict, Any

from biodm.components import Base
from biodm.utils.security import UserInfo
from biodm.utils.sqla import UpsertStmt
from biodm.utils.utils import classproperty
from .dbservice import CompositeEntityService


class K8Service(CompositeEntityService):
    """Manages kubernetes instances.
    """
    @classproperty
    def k8s(cls):
        return cls.app.k8s

    async def write(
        self,
        data: List[Dict[str, Any]] | Dict[str, Any],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Base | List[Base] | UpsertStmt | List[UpsertStmt]:
        """Submits manifest to kubernetes cluster before inserting into DB."""
        # K8s
        # data = {

        # }
        # DB
        return await super().write(data, user_info=user_info, stmt_only=stmt_only, **kwargs)
