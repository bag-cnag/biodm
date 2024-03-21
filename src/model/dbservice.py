from contextlib import AsyncExitStack
from inspect import getfullargspec
from abc import ABC, ABCMeta, abstractmethod
from typing import List, Any, overload, Tuple

from sqlalchemy.sql import Select, Insert, Update, Delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_utils import get_class_by_table
from starlette.datastructures import QueryParams

from exceptions import MissingDB, FailedRead, FailedDelete, FailedUpdate, MissingService
from model import Base
from utils.utils import unevalled_all, unevalled_or, to_it


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
    """Root Service class: manages database transactions for entities."""

    def in_session(db_exec):
        """Decorator that ensures db_exec receives a session.

        session object is either passed as an argument (from nested obj creation)
            or a new context manager is opened.
        contextlib.AsyncExitStack() below allows for conditional context management.
        """
        # Restrict decorator on functions that looks like this.
        argspec = getfullargspec(db_exec)
        assert('self' in argspec.args)
        assert(any((
            'stmt'      in argspec.args,
            'item'      in argspec.args,
            'composite' in argspec.args
        )))
        # TODO: debug
        # assert(argspec.annotations[argspec.args[1]] in (
        #     Insert, Delete, Select, Update, Base, 
        #     # CompositeEntityService.CompositeInsert
        #     ))
        assert('session' in argspec.args)
        #

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
    async def create_update(self, **kwargs):
        """CREATE UPDATE."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError

    @abstractmethod
    async def filter(self, **kwargs):
        """FILTER."""
        raise NotImplementedError


class UnaryEntityService(DatabaseService):
    """Generic Service class for non-composite entities."""
    def __init__(self, app, table: Base, pk: Tuple[str, ...], *args, **kwargs) -> None:
        # Entity info.
        self._table = table
        # Enable entity - service linkage.
        table.svc = self
        self.pk = tuple(table.col(key) for key in pk)
        self.relationships = table.relationships()

        super(UnaryEntityService, self).__init__(app=app, *args, **kwargs)

    @property
    def table(self) -> Base:
        """Return"""
        return self._table

    @overload
    async def create(self, data, stmt_only: bool=True) -> Insert:
        """..."""

    async def create(self, data, stmt_only: bool=False) -> Base | List[Base]:
        """CREATE one or many rows. data: schema validation result."""
        idx_elm = [k.name for k in self.pk]

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

    async def create_update(self, id, data: dict) -> Base:
        """CREATE or UPDATE one row."""
        kw = {
            pk.name: pk.type.python_type(val)
            for pk, val in zip(self.pk, to_it(id))
        }
        # TODO: fix: this, doesn't work when trying to update the entire pk
        # try:
        #     item = await self.read(id)
        #     for key, val in data.items():
        #         item.__setattr__(key,  val)
        # except FailedRead as e:
        #     for field, val in zip(self.pk, id):
        #         data[field] = val
        #         item = self.table(**data)
        # return await self._merge(item)
        # Merge
        item = self.table(**kw, **data)
        return await self._merge(item)

    async def filter(self, query_params: QueryParams) -> List[Base]:
        """READ rows filted on query parameters."""
        stmt = select(self.table)
        for dskey, csval in query_params.items():
            attr = dskey.split('.')
            values = csval.split(',')
            # exclude = False
            # if attr == 'exclude' and values == 'True':
            #     exclude = True

            # In case no value is associated we should be in the case of a numerical operator.
            operator = None
            SUPPORTED_OPERATORS = ('gt', 'ge', 'lt', 'le')
            if not csval:
                input_op = attr.pop()
                match input_op.strip(')').split('('):
                    case [('gt'| 'ge' | 'lt' | 'le') as op, arg]:
                        operator = (op, arg)
                    case _:
                        raise ValueError(
                            f"Expecting either 'field=v1,v2' pairs or integrer"
                            f" operators 'field.op(v)' op in {SUPPORTED_OPERATORS}")
            elif any(op in dskey for op in SUPPORTED_OPERATORS):
                raise ValueError("'field.op()=value' type of query is not yet supported.")

            # For every nested entity of the attribute, join table.
            table = self.table
            for nested in attr[:-1]:
                jtn = table.target_table(nested)
                if jtn is None:
                    raise ValueError(f"Invalid nested entity name {nested}.")
                jtable = get_class_by_table(Base, jtn)
                stmt = stmt.join(jtable)
                table = jtable

            # Get field info from last joined table.
            col, ctype = table.colinfo(attr[-1])

            # Numerical operators.
            if operator:
                if ctype not in (int, float):
                    raise ValueError(
                        f"Using operators methods {SUPPORTED_OPERATORS} in /search is"
                        " only allowed for numerical fields."
                    )
                op, val = operator
                op = col.__getattr__(f"__{op}__")
                stmt = stmt.where(op(ctype(val)))

            # Wildcards.
            wildcards = []
            for i, v in enumerate(values):
                if '*' in v:
                    wildcards.append(values.pop(i))
                elif v == '':
                    values.pop(i)

            if len(wildcards) > 0 and ctype is not str:
                raise ValueError(
                    f"Using wildcards '*' in /search is only allowed"
                     " for text fields.")

            stmt = stmt.where(
                unevalled_or(
                    col.like(str(w).replace("*", "%"))
                    for w in wildcards
            )) if wildcards else stmt

            # Regular equality conditions.
            stmt = stmt.where(
                unevalled_or(
                    col == ctype(v)
                    for v in values
            )) if values else stmt

            # if exclude:
            #     stmt = select(self.table.not_in(stmt))
        return await self._select_many(stmt)

    async def read(self, id) -> Base:
        """READ one row."""
        stmt = select(self.table).where(self.gen_cond(id))
        return await self._select(stmt)

    async def update(self, id, data: dict) -> Base:
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

    async def _insert(self, stmt: Insert | CompositeInsert, session: AsyncSession=None) -> Base | None:
        """Redirect in case of composite insert. No need for session decorator."""
        if isinstance(stmt, self.CompositeInsert):
            return await self._insert_composite(stmt, session)
        else:
            return await super()._insert(stmt, session)

    async def _insert_many(self, stmt: Insert | List[CompositeInsert], session: AsyncSession=None) -> List[Base]:
        """Redirect in case of composite insert. No need for session decorator."""
        if isinstance(stmt, Insert):
            return await super()._insert_many(stmt, session)
        else:
            return [await self._insert(composite, session) for composite in stmt]

    @DatabaseService.in_session
    async def _insert_composite(self, composite: CompositeInsert, session: AsyncSession) -> (Base | None):
        """INSERT composite entity."""
        # Insert all nested objects + item (last).
        for sub in composite.nested + [composite.item]:
            item = await self._insert(sub, session)
        # Populate item with delayed lists.
        for key in composite.delayed.keys():
            items = await self._insert_many(composite.delayed[key], session)
            getattr(item, key).update(items)
        if item: return item

    async def create(self, data, stmt_only: bool=False) -> Base | CompositeInsert:
        """CREATE, accounting for nested entitites."""
        stmts = []
        delayed = {}

        # For all table relationships, check whether data contains that item.
        for key, rel in self.relationships.items():
            sub = data.get(key)
            if not sub: continue

            # Retrieve associated service.
            svc = get_class_by_table(Base, rel.target).svc

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
