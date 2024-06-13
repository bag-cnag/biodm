from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    import logging
    from biodm.api import Api
    from biodm.components import Base
    from biodm.utils import UserInfo


class ApiComponent(ABC):
    """Abstract API component, refrencing main server class and its loggger.

    :param app: Reference to running server class.
    :type app: class:`biodm.Api`
    """
    app: Api
    logger: logging.logger

    def __init__(self, app: Api):
        self.__class__.app = app
        self.__class__.logger = app.logger


class ApiService(ApiComponent):
    """Service base class."""
    @abstractmethod
    async def create(
        self,
        data: Dict[str, Any] | List[Dict[str, Any]],
        stmt_only: bool,
        user_info: UserInfo,
        **kwargs
    ) -> Base | List[Base] | str:
        raise NotImplementedError

    @abstractmethod
    async def read(
        self,
        pk_val: List[Any],
        fields: List[str],
        user_info: UserInfo,
        **kwargs
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def filter(
        self,
        fields: List[str],
        params: Dict[str, str],
        user_info: UserInfo,
        **kwargs
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        pk_val: List[Any],
        user_info: UserInfo,
        **kwargs
    ) -> None:
        raise NotImplementedError
