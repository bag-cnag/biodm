from typing import TYPE_CHECKING

from sqlalchemy import (
    inspect, Column, Integer, text, String, TIMESTAMP, ForeignKey,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped
from sqlalchemy.orm.relationships import Relationship

if TYPE_CHECKING:
    from core.tables import User


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


class S3File(object):
    """Class to use in order to have a file managed on S3 bucket associated to this table
        
        Defaults internal fields that are expected by S3Service."""
    id = Column(Integer, nullable=False, primary_key=True)
    filename = Column(String(100), nullable=False)
    extension = Column(String(10), nullable=False)
    url = Column(String(200), nullable=False)

    @declared_attr
    def id_user_uploader(_):
        return Column(ForeignKey("USER.id"),    nullable=False)

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship(foreign_keys=[cls.id_user_uploader], lazy="immediate")

    emited_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), 
                       nullable=False)
    validated_at = Column(TIMESTAMP(timezone=True), nullable=True)
