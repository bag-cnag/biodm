from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.relationships import Relationship


class Base(DeclarativeBase, AsyncAttrs):
    """Base class for ORM declarative Tables."""
    # Enable entity - service linkage.
    svc = None

    @classmethod
    def relationships(cls):
        return inspect(cls).mapper.relationships

    @classmethod
    def target_table(cls, name):
        """Returns target table of a property."""
        c = cls.col(name).property
        return c.target if isinstance(c, Relationship) else None

    @classmethod
    def col(cls, name):
        """Returns columns object from name."""
        return cls.__dict__[name]

    @classmethod
    def colinfo(cls, name):
        """Return column and associated python type for conditions."""
        c = cls.col(name)
        return c, c.type.python_type

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate tablename."""
        return cls.__name__.upper()
