from contextlib import asynccontextmanager, AsyncExitStack
from inspect import getfullargspec
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)

from biodm.components import Base
from biodm.exceptions import PostgresUnavailableError


class DatabaseManager(object):
    def __init__(self, app, sync=False) -> None:
        self.app = app
        self.database_url = app.config.DATABASE_URL if sync else self.async_database_url(app.config.DATABASE_URL)
        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=app.config.DEBUG,
            )
            self.async_session = async_sessionmaker(
                self.engine, 
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except Exception as e:
            raise PostgresUnavailableError(f"Failed to initialize connection to Postgres: {e.error_message}")

    @staticmethod
    def async_database_url(url) -> str:
        return url.replace("postgresql://", "postgresql+asyncpg://")

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
        This decorator guarantees exactly 1 session per request, contextlib.AsyncExitStack() below allows for conditional context management.

        Also performs serialization **within the session**: important for lazy nested attributes) when passed a serializer.

        It is doing so by extracting 'serializer' argument (sometimes explicitely, sometimes implicitely passed around using kwargs dict)
        !! Thus all 'not final' functions (i.e. defined outside of this class) onto which this decorator is applied should pass down **kwargs dictionary.
        """

        # Weak protection: restrict decorator on functions that looks like this.
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
            if obj.app.config.DEV and serializer:
                from biodm.components.services import DatabaseService
                assert(isinstance(obj, DatabaseService))

            async with AsyncExitStack() as stack:
                session = session if session else (
                    await stack.enter_async_context(obj.session()))
                res = await db_exec(obj, arg, session=session, **kwargs)

                if not serializer:
                    return res

                # Serialization has to be run sync.
                def serialize(_, res):
                    return serializer(res)
                return await session.run_sync(serialize, res)

        wrapper.__name__ = db_exec.__name__
        wrapper.__doc__ = db_exec.__doc__
        return wrapper
