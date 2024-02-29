from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)

from config import DATABASE_URL, DEBUG
from .table import Base


class DatabaseManager():
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

# ## Snippet for version In case needed one day:
# # SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# # def db():
#     # db = SessionLocal()
#     # try:
#     #     yield dbBase = declarative_base()

#     # finally:
#     #     db.close()
# # Goes into db/session
# # from sqlalchemy import create_engine
# # engine = create_engine(SQLALCHEMY_DATABASE_URL)
