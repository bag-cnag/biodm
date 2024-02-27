import logging
import importlib
from abc import ABC, ABCMeta, abstractmethod
from typing import List, Any

from sqlalchemy import (
    insert, 
    select, 
    update, 
    delete, 
    Result,
    inspect
)
from sqlalchemy.sql import Insert, Select, Update, Delete
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import MissingDB, FailedRead, FailedDelete, FailedUpdate
from model import Base
import model
import pdb


class Singleton(ABCMeta):
    """Singleton pattern as metaclass."""
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
    def db_session(self) -> AsyncSession:
        """Yields DatabaseManager.session()"""
        if not self.app.db:
            raise MissingDB(f"No database attached to {self}.")
        return self.app.db.session()

    async def _insert(self, stmt: Insert) -> (Any | None):
        """INSERT one into database."""
        async with self.db_session as s:
            row = await s.scalar(stmt)
        if row: return row

    async def _insert_many(self, stmt: Insert) -> List[Any]:
        """INSERT many into database."""
        async with self.db_session as s:
            rows = await s.scalars(stmt)
        return rows
    
    async def _insert_nested(self, tpl: tuple[Insert, List[Insert]]) -> (Any | None):
        """Insert one row and associated nested relationships rows."""
        s_item, ls_nested = tpl
        async with self.db_session as s:
            # Insert all dependencies: important to await.
            for sub in ls_nested:
                await s.scalar(sub)
            # Insert item
            row = await s.scalar(s_item)
        if row: return row

    async def _select(self, stmt: Select) -> (Any | None):
        """SELECT one from database."""
        async with self.db_session as s:
            result = (await s.execute(stmt)).scalar()
        if result: return result
        raise FailedRead("Query returned no result.")

    async def _select_many(self, stmt: Select) -> List[Any]:
        """SELECT many from database."""
        async with self.db_session as s:
            return (await s.execute(stmt)).scalars().unique()

    async def _update(self, stmt: Update):
        """UPDATE database entry."""
        async with self.db_session as s:
            result = (await s.execute(stmt)).scalar()
        if result: return result
        raise FailedUpdate("Query updated no result.")

    async def _merge(self, item: Any):
        """Use session.merge feature: sync local object with one from db."""
        async with self.db_session as s:
            item = await s.merge(item)
        if item: return item
        raise FailedUpdate("Query updated no result.")

    async def _delete(self, stmt: Delete) -> None:
        """DELETE one row."""
        async with self.db_session as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                raise FailedDelete("Query deleted no rows.")

    @abstractmethod
    async def create(self, stmt_only=False, **kwargs):
        """CREATE one row."""
        raise NotImplementedError

    @abstractmethod
    async def create_many(self, stmt_only=False, **kwargs):
        """CREATE many rows."""
        raise NotImplementedError

    @abstractmethod
    async def read(self, **kwargs):
        """READ one row."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, **kwargs):
        """UPDATE one row."""
        raise NotImplementedError

    @abstractmethod
    async def find_all(self, **kwargs):
        """READ all rows."""
        raise NotImplementedError

    @abstractmethod
    async def create_update(self, **kwargs):
        """CREATE UPDATE."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError


class UnaryEntityService(DatabaseService):
    """Generic Service class for non-composite entities with atomic primary_key."""
    def __init__(self, app, table: Base, id: str="id", *args, **kwargs):
        self._table = table

        # Set and verify id
        self.id = table.__dict__[id]
        assert(self.id.primary_key)
        self.id_type = self.id.type.python_type

        super(UnaryEntityService, self).__init__(app=app, *args, **kwargs)

    @property
    def table(self) -> Base:
        """Return"""
        return self._table

    async def create(self, data, stmt_only=False) -> table:
        """CREATE one row. data: schema validation result."""
        # pdb.set_trace()
        stmt = insert(self.table).values(**data).returning(self.table)
        return stmt if stmt_only else await self._insert(stmt)

    async def create_many(self, data, stmt_only=False) -> List[table]:
        """CREATE many rows."""
        stmt = insert(self.table).values(data).returning(self.table)
        return stmt if stmt_only else await self._insert_many(stmt)

    async def create_update(self, id, data) -> table:
        """CREATE or UPDATE one row."""
        item = self.table(**{self.id: self.id_type(id)}, **data)
        return await self._merge(item)

    async def find_all(self) -> List[table]:
        """READ all rows."""
        stmt = select(self.table)
        return await self._select_many(stmt)

    async def read(self, id) -> table:
        """READ one row."""
        stmt = select(self.table).where(self.id == self.id_type(id))
        return await self._select(stmt)

    async def update(self, id, data) -> table:
        """UPDATE one row."""
        stmt = update(self.table
                ).where(self.id == self.id_type(id)
                    ).values(**data
                        ).returning(self.table)
        return await self._update(stmt)

    async def delete(self, id):
        """DELETE."""
        stmt = delete(self.table).where(self.table.id == self.id_type(id))
        return await self._delete(stmt)


class CompositeEntityService(UnaryEntityService):
    @property
    def table(self) -> Base:
        """Return"""
        return self._table

    async def create(self, data, stmt_only=False) -> table:
        """CREATE one row, accounting for nested entitites."""
        stmts = []
        mapper = inspect(self.table).mapper
        rels = mapper.relationships

        # For all table relationships, check whether data contains that item.
        for key in rels.keys():
            sub = data.get(key)
            if sub:
                # Retrieve associated service.
                target_table = rels[key].target
                svc = target_table.name.capitalize() + "Service"
                svc = getattr(getattr(model, "services"), svc)()

                # Build statements for nested entities.
                nested_stmt = await svc.create(sub, stmt_only=True)
                stmts.append(nested_stmt)

                # Remove from data dict to avoid errors in item stmt.
                del data[key]

        # Statement for original item.
        stmt = insert(self.table).values(**data).returning(self.table)
        return stmts if stmt_only else await self._insert_nested((stmt, stmts))
