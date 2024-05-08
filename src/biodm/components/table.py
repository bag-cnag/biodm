from __future__ import annotations
from typing import TYPE_CHECKING


from sqlalchemy import (
    inspect, Column, Integer, text, String, TIMESTAMP, ForeignKey, UUID
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped
from sqlalchemy.orm.relationships import Relationship

if TYPE_CHECKING:
    from biodm.tables import User, Group, ListGroup
    from biodm.components.services import DatabaseService


class Base(DeclarativeBase, AsyncAttrs):
    """Base class for ORM declarative Tables."""
    # Enable entity - service linkage.
    svc: DatabaseService

    @classmethod
    def relationships(cls):
        return inspect(cls).mapper.relationships

    @classmethod
    def target_table(cls, name):
        """Returns target table of a property."""
        c = cls.col(name).property
        return c.target if isinstance(c, Relationship) else None

    @classmethod
    def pk(cls):
        return (
            str(pk).rsplit('.', maxsplit=1)[-1] 
            for pk in cls.__table__.primary_key.columns
        )

    @classmethod
    def col(cls, name):
        """Return columns object from name."""
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


class S3File:
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
    @classmethod
    def user(cls) -> Mapped["User"]:
        return relationship(foreign_keys=[cls.id_user_uploader], lazy="select")

    emited_at = Column(TIMESTAMP(timezone=True),
                       server_default=text('now()'), 
                       nullable=False)
    validated_at = Column(TIMESTAMP(timezone=True))


class Permission:
    """Class that produces necessary fields to declare ressource permissions for an entity.
    
        for each action in [CREATE, READ, UPDATE, DELETE, DOWNLOAD]:
            

    """
    # def __init_subclass__(cls, **kwargs) -> None:
    #     """To restrict on some tables."""
    #     if S3File in cls.__bases__:
    #         cls.id_ls_download = declared_attr(cls.id_ls_download)
    #         cls.ls_download = declared_attr(cls.ls_download)
    #     super().__init_subclass__(**kwargs)

    @declared_attr
    def id_ls_download(_):
        return Column(ForeignKey("LISTGROUP.id"), nullable=True)

    @declared_attr
    @classmethod
    def ls_download(cls) -> Mapped["ListGroup"]:
        return relationship("ListGroup", foreign_keys=[cls.id_ls_download], lazy="select")

    @declared_attr
    def id_ls_create(_):
        return Column(ForeignKey("LISTGROUP.id"), nullable=True)

    @declared_attr
    @classmethod
    def ls_create(cls) -> Mapped["ListGroup"]:
        return relationship("ListGroup", foreign_keys=[cls.id_ls_create], lazy="select")

    @declared_attr
    def id_ls_read(_):
        return Column(ForeignKey("LISTGROUP.id"), nullable=True)

    @declared_attr
    @classmethod
    def ls_read(cls) -> Mapped["ListGroup"]:
        return relationship("ListGroup", foreign_keys=[cls.id_ls_read], lazy="select")

    @declared_attr
    def id_ls_update(_):
        return Column(ForeignKey("LISTGROUP.id"), nullable=True)

    @declared_attr
    @classmethod
    def ls_update(cls) -> Mapped["ListGroup"]:
        return relationship("ListGroup", foreign_keys=[cls.id_ls_update], lazy="select")

    @declared_attr
    def name_owner_group(_):
        return Column(ForeignKey("GROUP.name"), nullable=True)

    @declared_attr
    @classmethod
    def owner_group(cls) -> Mapped["Group"]:
        return relationship(foreign_keys=[cls.name_owner_group], lazy="select")
