from __future__ import annotations
from contextlib import asynccontextmanager, AsyncExitStack
from typing import AsyncGenerator, TYPE_CHECKING, Callable, Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from biodm import Scope, config
from biodm.component import ApiComponent
from biodm.exceptions import PostgresUnavailableError, DBError

if TYPE_CHECKING:
    from biodm.api import Api
    from biodm.components.services import DatabaseService


class DatabaseManager(ApiComponent):
    """Manages DB side query execution."""
    def __init__(self, app: Api) -> None:
        super().__init__(app=app)
        self.database_url: str = self.async_database_url(config.DATABASE_URL)
        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=Scope.DEBUG in app.scope,
            )
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except SQLAlchemyError as e:
            raise PostgresUnavailableError(f"Failed to connect to DB") from e

    @staticmethod
    def async_database_url(url) -> str:
        """Adds a matching async driver to a database url."""
        match url.split("://"):
            case ["postgresql", _]:
                return url.replace( # type: ignore [unreachable]
                    "postgresql://", "postgresql+asyncpg://"
                )
            case ["sqlite", _]:
                return url.replace( # type: ignore [unreachable]
                    "sqlite://", "sqlite+aiosqlite://"
                )
            case _:
                raise DBError(
                    "Only ['postgresql', 'sqlite'] backends are supported at the moment."
                )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Opens and yields a new AsyncSession."""
        try:
            async with self.async_session() as session:
                yield session
                await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

    async def init_db(self) -> None:
        """Drop all tables and create them."""
        from biodm.components import Base
        Base.setup_permissions(self.app)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    def in_session(db_exec: Callable) -> Callable:
        """Decorator that ensures db_exec receives a session.
            Session object is either passed as an argument (from nested obj creation) or a new context
            manager is opened. This decorator guarantees exactly 1 session per request.

        Also performs serialization :strong:`within a sync session`:

        - Avoids errors in case serializing acceses a lazy attribute
        - All functions applying this decorator should pass down some `**kwargs`

        """
        async def wrapper(*args, **kwargs) -> Any | str | None:
            """ Produce and passes down a session if needed.
                Finally after the function returns, serialization is applied if needed.
            """
            serializer = kwargs.pop('serializer', None)

            # conditional context management.
            async with AsyncExitStack() as stack:
                self = args[0]
                session = kwargs.pop('session', None)
                # Ensure session.
                session = (
                    session if session
                    else await stack.enter_async_context(self.app.db.session())
                )
                # Call and serialize result if requested.
                db_result = await db_exec(*args, session=session, **kwargs)
                result = await session.run_sync(
                    lambda _, data: serializer(data), db_result
                ) if serializer else db_result
            return result

        wrapper.__annotations__ = db_exec.__annotations__
        wrapper.__name__ = db_exec.__name__
        wrapper.__doc__ = db_exec.__doc__
        return wrapper
