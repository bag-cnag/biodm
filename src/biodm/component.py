from __future__ import annotations
from abc import abstractmethod, ABCMeta
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import logging
    from biodm.api import Api
    from biodm.components import Base
    from biodm.utils import UserInfo
    from biodm.utils.sqla import InsertStmt


class ApiComponent(metaclass=ABCMeta):
    """Abstract API component, refrencing main server class and its loggger.

    :param app: Reference to running server class.
    :type app: class:`biodm.Api`
    """
    app: Api
    logger: logging.Logger # type: ignore [name-defined]

    def __init__(self, app: Api) -> None:
        self.__class__.app = app
        self.__class__.logger = app.logger


class ApiService(ApiComponent, metaclass=ABCMeta):
    """Service base class."""
    @abstractmethod
    async def create(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool = False,
        user_info: UserInfo | None = None,
        **kwargs
    ) -> InsertStmt | List[InsertStmt] | Base | List[Base]:
        raise NotImplementedError

    @abstractmethod
    async def read(
        self,
        pk_val: List[Any],
        fields: List[str],
        user_info: UserInfo | None = None,
        **kwargs
    ) -> Base:
        raise NotImplementedError

    @abstractmethod
    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        user_info: UserInfo | None = None,
        **kwargs
    ) -> List[Base]:
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        pk_val: List[Any],
        user_info: UserInfo | None = None,
        **kwargs
    ) -> None:
        raise NotImplementedError
