import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import List

from sqlalchemy import insert, Result

from app import Api
from exceptions import MissingDB, FailedRead, FailedDelete


class Singleton(ABCMeta):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class BaseService(ABC):
    def __init__(self, app: Api):
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
        # for d in data:
        async with self.db_session as s:
            s.add_all(data)
        
    async def _read(self, stmt):
        """Select 1 from database."""
        async with self.db_session as s:
            result = (await s.execute(stmt)).scalar()
            if not result:
                raise FailedRead("Query returned no result.")

            return result
    
    async def _update(self, stmt):
        """Update database entry TODO:"""
        raise NotImplementedError
        async with self.db_session as s:
            result = (await s.execute(stmt)).scalar()
            if not result:
                raise FailedRead("Query returned no result.")

            return result

    async def _delete(self, stmt):
        """Delete database entry."""
        raise NotImplementedError
        async with self.db_session as s:
            async with s.begin():
                result = await s.execute(stmt)
                if result.rowcount == 0:
                    raise FailedDelete("Query deleted no rows.")

    async def _find_all(self, stmt):
        """Select all from database."""
        raise NotImplementedError
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
    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError

    @abstractmethod
    async def find_all(self, **kwargs):
        """Get all rows."""
        raise NotImplementedError
