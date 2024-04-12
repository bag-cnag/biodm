from contextlib import asynccontextmanager, AsyncExitStack
from inspect import getfullargspec
from typing import AsyncGenerator, Any, List

from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy.sql import Select, Insert, Update, Delete

from core.exceptions import FailedRead, FailedDelete, FailedUpdate
from instance.config import DATABASE_URL, DEBUG
from ..table import Base

class DatabaseManager(object):
    def __init__(self, sync=False) -> None:
        self.database_url = DATABASE_URL if sync else self.async_database_url()
        self.engine = create_async_engine(
            self.database_url,
            echo=DEBUG,
        )
        self.async_session = async_sessionmaker(
            self.engine, 
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @staticmethod
    def async_database_url() -> str:
        return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        try:
            async with self.async_session() as session:
                yield session
                await session.commit()
        except:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    def in_session(db_exec):
        """Decorator that ensures db_exec receives a session.

        session object is either passed as an argument (from nested obj creation)
            or a new context manager is opened.
        contextlib.AsyncExitStack() below allows for conditional context management.

        Also performs serialization **within the session**: important for lazy nested attributes) when passed a serializer.
        It is doing so by extracting 'serializer' argument (sometimes explicitely, sometimes implicitely passed around using kwargs dict)
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
        async def wrapper(obj, arg, session: AsyncSession=None, serializer=None):
            async with AsyncExitStack() as stack:
                session = session if session else (
                    await stack.enter_async_context(obj.session()))
                res = await db_exec(obj, arg, session)
                return serializer(res) if serializer else res
        return wrapper

    @in_session
    async def _insert(self, stmt: Insert, session: AsyncSession) -> (Any | None):
        """INSERT one into database."""
        return await session.scalar(stmt)

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
