from __future__ import annotations
from abc import abstractmethod, ABCMeta
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import logging
    from biodm.api import Api
    from biodm.components import Base
    from biodm.utils import UserInfo
    from biodm.utils.sqla import UpsertStmt


class ApiComponent(metaclass=ABCMeta):
    """Abstract API component, refrencing main server class and its loggger.

    :param app: Reference to running server class.
    :type app: class:`biodm.Api`
    """
    app: Api
    logger: logging.Logger

    def __init__(self, app: Api) -> None:
        self.__class__.app = app
        self.__class__.logger = app.logger


class ApiManager(ApiComponent, metaclass=ABCMeta):
    """Manager base class.
    A manager represents an external service dependency.
    It holds a connection object and relevant primitives for data state change."""
    @property
    @abstractmethod
    def endpoint(self) -> str:
        """External service endpoint."""
        raise NotImplementedError


class ApiService(ApiComponent, metaclass=ABCMeta):
    """Service base class.
    A Service acts as a translation layer between a controller receiving a request
    and managers executing data state change."""
    @abstractmethod
    async def write(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        partial_data: bool = False,
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs: Dict[str, Any]
    ) -> UpsertStmt | List[UpsertStmt] | Base | List[Base]:
        raise NotImplementedError

    @abstractmethod
    async def read(
        self,
        pk_val: List[Any],
        fields: List[str],
        user_info: UserInfo | None = None,
        **kwargs: Dict[str, Any]
    ) -> Base:
        raise NotImplementedError

    @abstractmethod
    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        user_info: UserInfo | None = None,
        **kwargs: Dict[str, Any]
    ) -> List[Base]:
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        pk_val: List[Any],
        user_info: UserInfo | None = None,
        **kwargs: Dict[str, Any]
    ) -> None:
        raise NotImplementedError
