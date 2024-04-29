from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from starlette.responses import Response

if TYPE_CHECKING:
    import logging
    from biodm.api import Api

class ApiComponent(ABC):
    """Abstract API component, refrencing main server class and its loggger."""
    app: Api
    logger: logging.logger

    def __init__(self, app: Api):
        self.__class__.app = app
        self.__class__.logger = app.logger

class CRUDApiComponent(ApiComponent, ABC):
    """API CRUD component Interface. Enforces CRUD methods on children classes."""
    @abstractmethod
    async def create(self, *args, **kwargs) -> Response:
        raise NotImplementedError

    @abstractmethod
    async def read(self, *args, **kwargs) -> Response:
        raise NotImplementedError

    @abstractmethod
    async def update(self, *args, **kwargs) -> Response:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, *args, **kwargs) -> Response:
        raise NotImplementedError
    
    @abstractmethod
    async def create_update(self, *args, **kwargs) -> Response:
        raise NotImplementedError
    
    @abstractmethod
    async def filter(self, *args, **kwargs) -> Response:
        raise NotImplementedError
