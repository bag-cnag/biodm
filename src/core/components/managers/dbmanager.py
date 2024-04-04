from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)

from core.components import Base
from instance.config import DATABASE_URL, DEBUG


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
