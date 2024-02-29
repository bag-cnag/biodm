import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import List, Any, overload, Tuple

from sqlalchemy import (
    insert, select, update,
    delete, Result, inspect
)
from sqlalchemy.sql import Insert, Select, Update, Delete
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import MissingDB, FailedRead, FailedDelete, FailedUpdate
from model import Base
import model
from utils.utils import unevalled_all, to_it
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

    async def _merge(self, item: Base) -> Base:
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
    """Generic Service class for non-composite entities."""
    def __init__(self, app, table: Base, id: (str | Tuple[str, ...])="id", *args, **kwargs):
        self._table = table
        # TODO: Change id to pk

        # Set and verify id: possible composite primary key.
        self.id = tuple(table.__dict__[i] for i in to_it(id))
        assert(i.primary_key for i in self.id)
        self.id_type = tuple(i.type.python_type for i in self.id)
        self.id_name = to_it(id)
 
        super(UnaryEntityService, self).__init__(app=app, *args, **kwargs)

    @property
    def table(self) -> Base:
        """Return"""
        return self._table

    @overload
    async def create(self, data, stmt_only: True) -> Insert:
        """..."""

    async def create(self, data, stmt_only: False) -> table | List[table]:
        """CREATE one or many rows. data: schema validation result."""
        if isinstance(data, list):
            stmt = insert(self.table).values(data).returning(self.table)
            return stmt if stmt_only else await self._insert_many(stmt)
        else:
            stmt = insert(self.table).values(**data).returning(self.table)
            return stmt if stmt_only else await self._insert(stmt)

    def gen_cond(self, values):
        """Generates WHERE condition from pk definition and values."""
        return unevalled_all((
                pk == cast(val)
                for pk, cast, val in zip(
                    self.id,
                    self.id_type,
                    to_it(values)
                )
            ))

    async def create_update(self, id, data) -> table:
        """CREATE or UPDATE one row."""
        kw = {
            id: id_type(value) 
            for id, id_type, value in zip(
                self.id_name, 
                self.id_type, 
                to_it(id)
            )
        }
        item = self.table(**kw, **data)
        return await self._merge(item)

    async def find_all(self) -> List[table]:
        """READ all rows."""
        stmt = select(self.table)
        return await self._select_many(stmt)

    async def read(self, id) -> table:
        """READ one row."""
        stmt = select(self.table).where(self.gen_cond(id))
        return await self._select(stmt)

    async def update(self, id, data) -> table:
        """UPDATE one row."""
        stmt = update(self.table
                ).where(self.gen_cond(id)
                    ).values(**data
                        ).returning(self.table)
        return await self._update(stmt)

    async def delete(self, id):
        """DELETE."""
        stmt = delete(self.table).where(self.gen_cond(id))
        return await self._delete(stmt)


class CompositeInsert(object):
    """Class to manage composite entities insertions."""
    def __init__(self, item: Insert, nested: List[Insert]=[], delayed: dict={}) -> None:
        self.item = item
        self.nested = nested
        self.delayed = delayed


class CompositeEntityService(UnaryEntityService):
    @property
    def table(self) -> Base:
        """Return"""
        return self._table

    async def _insert(self, stmt: (Insert| CompositeInsert)) -> Any | None:
        """Redirect in case of composite insert."""
        if isinstance(stmt, CompositeInsert):
            return self._insert_composite(stmt)
        else:
            await super()._insert(stmt)

    # async def _insert_many(self, stmt: Insert) -> List[Any]:
    #     return await super()._insert_many(stmt)

    async def _insert_composite(self, composite: CompositeInsert) -> (Any | None):
        """Insert a composite entity."""
        # TODO: take out session for all _statement execution functions.
        async with self.db_session as s:
            # Insert all nested objects (await !)
            for sub in composite.nested:
                # TODO: handle nested composites
                # if isinstance(sub, CompositeInsert):
                #     await 
                await s.scalar(sub)
            # Insert item
            item = await s.scalar(composite.item)
            # Populate with delayed lists
            for key in composite.delayed.keys():
                # TODO: handle list of composites
                items = await s.scalars(composite.delayed[key])
                getattr(item, key).update(items)
        if item: return item

    async def create(self, data, stmt_only=False) -> Base | CompositeInsert:
        """CREATE, accounting for nested entitites."""
        stmts = []
        delayed = {}
        rels = inspect(self.table).mapper.relationships

        # For all table relationships, check whether data contains that item.
        for key in rels.keys():
            rel = rels[key]
            sub = data.get(key)
            if not sub: continue

            # Retrieve associated service.
            target_table = rel.target
            svc = target_table.name.capitalize() + "Service"
            svc = getattr(getattr(model, "services"), svc)()

            # Get statement(s) for nested entity:
            nested_stmt = await svc.create(sub, stmt_only=True)

            # Single nested entity.
            if isinstance(sub, dict):
                stmts += [nested_stmt]
            # List of entities: one - to - many relationship.
            elif isinstance(sub, list):
                delayed[key] = nested_stmt
            else:
                raise ValueError("Expecting nested entities to be either passed as dict or list.")
            # Remove from data dict to avoid errors on building item statement.
            del data[key]

        # Statement for original item.
        stmt = insert(self.table).values(**data).returning(self.table)
        # Pack.
        composite = CompositeInsert(item=stmt, nested=stmts, delayed=delayed)

        return composite if stmt_only else await self._insert_composite(composite)
