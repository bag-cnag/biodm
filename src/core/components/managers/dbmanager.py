from contextlib import asynccontextmanager, AsyncExitStack
from inspect import getfullargspec
from typing import AsyncGenerator, Any, List

from sqlalchemy import ScalarResult
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy_utils import get_class_by_table
# from sqlalchemy.sql import Select, Insert, Update, Delete
from sqlalchemy.orm.collections import InstrumentedList, InstrumentedSet

from core.utils.utils import to_it # it_to, 
from instance.config import DATABASE_URL, DEBUG, DEV
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
        !! Thus all 'not final' functions (i.e. defined outside of this class) onto which this decorator is applied should pass down **kwargs dictionary.
        """

        # Weak protection: restrict decorator on functions that looks like this.
        if DEV:
            argspec = getfullargspec(db_exec)
            assert('self' in argspec.args)
            assert(any((
                'data'      in argspec.args,
                'stmt'      in argspec.args,
                'item'      in argspec.args,
                'composite' in argspec.args
            )))
            assert('session' in argspec.args)

        # Callable.
        async def wrapper(obj, arg, session: AsyncSession=None, serializer=None, **kwargs):
            if DEV and serializer:
                from core.components.services import DatabaseService
                assert(isinstance(obj, DatabaseService))

            async with AsyncExitStack() as stack:
                session = session if session else (
                    await stack.enter_async_context(obj.session()))
                res = await db_exec(obj, arg, session=session, **kwargs)

                if DEV:
                    assert(not isinstance(res, ScalarResult))

                if serializer:
                    """Ensures that lazy nested fields are loaded prior to serialization.

                    No cleaner way of doing it with SQLAlchemy
                    refer to: https://github.com/sqlalchemy/sqlalchemy/discussions/9731
                    """
                    attr_names = obj.table.relationships().keys()
                    # Fetch depth=2, TODO: Make it configurable ?
                    for item in to_it(res):
                        origin_table = item.svc.table.__table__
                        attributes = (await item.awaitable_attrs.__getattr__(name)
                                      for name in attr_names)
                        # async for doesn't support zip() nor making a dict out of attributes.
                        i = 0
                        async for attr in attributes:
                            attr_name, i = attr_names[i], i + 1
                            target = item.target_table(attr_name)
                            nested_rel = get_class_by_table(Base, target).relationships()
                            for nkey, rel in nested_rel.items():
                                # Avoid circular refreshing !!
                                if rel.target != origin_table and attr:
                                    await session.refresh(attr, attribute_names=[nkey])
                    return serializer(res)
                return res
        wrapper.__name__ = db_exec.__name__
        return wrapper
