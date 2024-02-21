from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr


class Base(AsyncAttrs, DeclarativeBase):
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate tablename."""
        return cls.__name__.upper()
