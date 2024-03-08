import logging

from contextlib import AsyncExitStack
from inspect import getfullargspec
from functools import wraps
from abc import ABC, ABCMeta, abstractmethod
from typing import List, Any, overload, Tuple


from sqlalchemy import (
    select, update,
    delete, Result, inspect
)
from sqlalchemy.sql import Insert, Select, Update, Delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from starlette.datastructures import QueryParams

from exceptions import MissingDB, FailedRead, FailedDelete, FailedUpdate, MissingService
from model import Base
import model
from utils.utils import unevalled_all, unevalled_or, to_it
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
    def in_session(db_exec):
        """Decorator that ensures db_exec receives a session.

        session object is either passed as an argument (from nested obj creation)
            or a new context manager is opened.
        contextlib.AsyncExitStack() below allows for conditional context management.
        """
        argspec = getfullargspec(db_exec)
        # Restrict decorator on functions that looks like this.
        assert('self' in argspec.args)
        assert(any((
            'stmt'      in argspec.args,
            'item'      in argspec.args,
            'composite' in argspec.args
        )))
        assert('session' in argspec.args)

        async def wrapper(self, arg, session: AsyncSession=None):
            async with AsyncExitStack() as stack:
                session = session if session else (
                    await stack.enter_async_context(self.app.db.session()))
                return await db_exec(self, arg, session)
        return wrapper

    @in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT one into database."""
        row = await session.scalar(stmt)
        if row: return row

    @in_session
    async def _insert_many(self, stmt: Insert, session: AsyncSession) -> List[Any]:
        """INSERT many into database."""
        return await session.scalars(stmt)

    @in_session
    async def _select(self, stmt: Select, session: AsyncSession) -> (Any | None):
        """SELECT one from database."""
        row = await session.scalar(stmt)
        if row: return row
        raise FailedRead("Query returned no result.")

    @in_session
    async def _select_many(self, stmt: Select, session: AsyncSession) -> List[Any]:
        """SELECT many from database."""
        return (await session.execute(stmt)).scalars().unique()

    @in_session
    async def _update(self, stmt: Update, session: AsyncSession):
        """UPDATE database entry."""
        result = await session.scalar(stmt)
        # result = (await session.execute(stmt)).scalar()
        if result: return result
        raise FailedUpdate("Query updated no result.")

    @in_session
    async def _merge(self, item: Base, session: AsyncSession) -> Base:
        """Use session.merge feature: sync local object with one from db."""
        item = await session.merge(item)
        if item: return item
        raise FailedUpdate("Query updated no result.")

    @in_session
    async def _delete(self, stmt: Delete, session: AsyncSession) -> None:
        """DELETE one row."""
        result = await session.execute(stmt)
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
    def __init__(self, app, table: Base, pk: Tuple[str, ...], *args, **kwargs):
        # Entity info.
        self._table = table
        self.pk = tuple(table.__dict__[key] for key in pk)
        self.relationships = inspect(table).mapper.relationships

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
        idx_elm = [k.name for k in self.pk]
        # pdb.set_trace()
        if isinstance(data, list):
            stmt = insert(self.table).values(data).returning(self.table)
            stmt = stmt.on_conflict_do_update(
                index_elements=idx_elm,
                set_={
                    key: getattr(stmt.excluded, key)
                    for key in stmt.excluded.keys()
                }
            )
            return stmt if stmt_only else await self._insert_many(stmt)
        else:
            stmt = insert(self.table).values(**data).returning(self.table
                    ).on_conflict_do_update(index_elements=idx_elm,
                                            set_=data)
            return stmt if stmt_only else await self._insert(stmt)

    def gen_cond(self, values):
        """Generates WHERE condition from pk definition and values."""
        return unevalled_all((
                pk == pk.type.python_type(val)
                for pk, val in zip(self.pk, to_it(values))
            ))

    async def create_update(self, id, data) -> table:
        """CREATE or UPDATE one row."""
        kw = {
            pk.name: pk.type.python_type(val)
            for pk, val in zip(self.pk, to_it(id))
        }
        item = self.table(**kw, **data)
        return await self._merge(item)

    async def find_all(self) -> List[table]:
        """READ all rows."""
        stmt = select(self.table)
        return await self._select_many(stmt)

    async def filter(self, query_params: QueryParams) -> List[table]:
        """READ rows filted on query parameters."""
        # TODO: clean a bit
        stmt = select(self.table)
        col = lambda k: self.table.__dict__[k]
        pytype = lambda k: col(k).type.python_type

        filter = []
        for key in query_params.keys():
            attr = key.split('.')
            val = query_params[key].split(',')

            # Simple attribute case
            if len(attr) == 1:
                attr = attr[0]
                clause = unevalled_or((
                    col(attr) == pytype(attr)(v)
                    for v in val
                ))
                filter.append(clause)

            # Nested entity case
            elif len(attr) == 2:
                attr, jfield = attr[0], attr[1]
                jtable = col(attr).property.target
                jcol = jtable.c[jfield]

                stmt = stmt.join(jtable, unevalled_or(
                    jcol == jcol.type.python_type(v)
                    for v in val
                ))
            else:
                # TODO: ?, Support deeper queries
                raise NotImplementedError("Search is only supported on immediately nested entities.")

        filter = unevalled_all(filter)
        stmt = stmt.where(filter)
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


class CompositeEntityService(UnaryEntityService):
    class CompositeInsert(object):
        """Class to manage composite entities insertions."""
        def __init__(self, item: Insert, nested: List[Insert]=[], delayed: dict={}) -> None:
            self.item = item
            self.nested = nested
            self.delayed = delayed

    @property
    def table(self) -> Base:
        """Return"""
        return self._table

    async def _insert(self, stmt: Insert | CompositeInsert, session: AsyncSession=None) -> Any | None:
        """Redirect in case of composite insert. No need for session decorator."""
        if isinstance(stmt, self.CompositeInsert):
            return await self._insert_composite(stmt, session)
        else:
            return await super()._insert(stmt, session)

    async def _insert_many(self, stmt: Insert | List[CompositeInsert], session: AsyncSession=None) -> List[Any]:
        """Redirect in case of composite insert. No need for session decorator."""
        if isinstance(stmt, Insert):
            return await super()._insert_many(stmt, session)
        else:
            return [await self._insert(composite, session) for composite in stmt]

    @DatabaseService.in_session
    async def _insert_composite(self, composite: CompositeInsert, session: AsyncSession) -> (Any | None):
        """Insert a composite entity."""
        # Insert all nested objects + item (last).
        for sub in composite.nested + [composite.item]:
            item = await self._insert(sub, session)
        # Populate item with delayed lists.
        for key in composite.delayed.keys():
            items = await self._insert_many(composite.delayed[key], session)
            getattr(item, key).update(items)
        if item: return item

    async def create(self, data, stmt_only=False) -> Base | CompositeInsert:
        """CREATE, accounting for nested entitites."""
        stmts = []
        delayed = {}
        # pdb.set_trace()

        # For all table relationships, check whether data contains that item.
        for key in self.relationships.keys():
            rel = self.relationships[key]
            sub = data.get(key)
            if not sub: continue

            # Retrieve associated service.
            target_table = rel.target
            svc_name = target_table.name.capitalize() + "Service"
            svc = getattr(getattr(model, "services"), svc_name, None)
            if not svc:
                raise MissingService(
                    f"Service {type(self).__name__} expected {svc_name} in model"
                    f" to insert nested entity."
                )
            svc = svc()

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

        # Pack & return.
        composite = self.CompositeInsert(item=stmt, nested=stmts, delayed=delayed)
        return composite if stmt_only else await self._insert_composite(composite)
