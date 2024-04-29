from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from biodm.api import Api

class Component(ABC):
    """Abstract API component, refrencing main server class and its loggger."""
    def __init__(self, app: Api) -> None:
        self.app = app
        self.logger = app.logger

class CRUDComponent(Component, ABC):
    """API CRUD component Interface. Enforces CRUD methods on children classes."""
    @abstractmethod
    async def create(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    async def read(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    async def update(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    async def delete(self, *args, **kwargs):
        raise NotImplementedError
    
    @abstractmethod
    async def create_update(self, *args, **kwargs):
        raise NotImplementedError
    
    @abstractmethod
    async def filter(self, *args, **kwargs):
        raise NotImplementedError
