import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import List

from sqlalchemy import insert, Result

from exceptions import MissingDB, FailedRead, FailedDelete, FailedUpdate
from model import Base

class Singleton(ABCMeta):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class BaseService(ABC):
    def __init__(self, app):
        self.logger = app.logger
        self.app = app


class DatabaseService(BaseService, metaclass=Singleton):
    @property
    def db_session(self):
        if not self.app.db:
            raise MissingDB(f"No database attached to {self}.")

        return self.app.db.session()

    async def _create(self, table, data):
        """Insert into database."""
        async with self.db_session as s:
            row = await s.scalar(
                insert(table).values(**data).returning(table)
            )
        return row

    async def _create_list(self, table, data: List) -> None:
        raise NotImplementedError

    async def _read(self, stmt):
        """Select 1 from database."""
        async with self.db_session as s:
            result = (await s.execute(stmt)).scalar()
            if result: return result
        raise FailedRead("Query returned no result.")

    async def _update(self, stmt):
        """Update database entry."""
        async with self.db_session as s:
            result = (await s.execute(stmt)).scalar()
            if result: return result
        raise FailedUpdate("Query updated no result.")

    async def _merge(self, table: Base, id: int, data: dict):
        """Use session.merge feature: sync local object with one from db."""
        item = None
        async with self.db_session as s:
            item = table(id=id, **data)
            item = await s.merge(item)
        if item: return item
        raise FailedUpdate("Query updated no result.")

    async def _delete(self, stmt) -> None:
        """Delete database entry."""
        async with self.db_session as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                raise FailedDelete("Query deleted no rows.")

    async def _find_all(self, stmt) -> List:
        """Select all from database."""
        async with self.db_session as s:
            return (await s.execute(stmt)).scalars().unique()

    @abstractmethod
    async def create(self, **kwargs):
        """CREATE."""
        raise NotImplementedError

    @abstractmethod
    async def read(self, **kwargs):
        """READ."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, **kwargs):
        """UPDATE."""
        raise NotImplementedError

    @abstractmethod
    async def create_update(self, **kwargs):
        """CREATE UPDATE."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError

    @abstractmethod
    async def find_all(self, **kwargs):
        """Get all rows."""
        raise NotImplementedError
