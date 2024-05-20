from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from re import T
from tkinter import N
from typing import TYPE_CHECKING, Any, List, Dict
import datetime

import marshmallow as ma
from sqlalchemy import (
    ForeignKeyConstraint, UniqueConstraint,
    inspect, Column, Integer, text, String, TIMESTAMP, ForeignKey, UUID
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, registry, Relationship, mapped_column, backref


if TYPE_CHECKING:
    from biodm.tables import User
    from biodm.components.services import DatabaseService
    from biodm.components.controllers import ResourceController

mapper_registry = registry()


class Base(DeclarativeBase, AsyncAttrs):
    """Base class for ORM declarative Tables.
 
    :param svc: Enable entity - service linkage
    :type svc: DatabaseService
    :param ctrl: Enable entity - controller linkage -> Resources tables only
    :type ctrl: ResourceController
    :param __permissions: Stores rules for user defined permissions on hierarchical entities
    :type __permissions: Dict
    """
    svc: DatabaseService
    ctrl: ResourceController = None
    __permissions: Dict = {}

    def __init_subclass__(cls, **kw: Any) -> None:
        """Sets up the rules according to permissions objects set on tables."""
        if hasattr(cls, "__permissions__"):
            # TODO: check that the relationship is many-to-one.
            cls._Base__permissions[cls.__name__] = (cls, cls.__permissions__)
        return super().__init_subclass__(**kw)

    @classmethod
    def setup_permissions(cls, app):
        """After tables have been added to Base, you may call this method to factor in changes.
        - Creates an associative table
            - indexed by Parent table pk
                - children hold parent id
            - holds listgroup objects mapped to enabled verbs
        - Set ref for Children controller

        -- Temporary for dev mode ?--.
        1. start by assuming straight composition
        2. extend to general case ?"""
        from biodm.components.services import CompositeEntityService
        from biodm.tables import ListGroup

        lut = {}
        for tname, (table, permissions) in cls._Base__permissions.items():
            lut[table] = {'entries': []}
            for pdef in permissions:
                enabled_verbs = [
                    verb
                    for verb, enabled in pdef.__dict__.items()
                    if enabled and verb != 'field'
                ]
                # TODO: handle no verbs case (simple propagation).
                """Declare new associative table:
                This Associative table uses a one-to-one relationship pattern to backref a field
                perm_{field} that holds permissions informations __without touching at Parent table
                definition__.

                The syntax is a little convoluted because most tools don't hanlde properly composite
                primary keys. However, the following nicely does the trick.

                All of this + associated schema so that an entity may be created with it's
                permission definitions passed as a nested object.

                This below achieves the following:
                class ASSO_PERM_{TABLE}_{FIELD}(Base):
                    pk_1_Table = Column(ForeignKey("TABLE".{pk_1}), primary_key=True)
                    ...
                    pk_n_Table =

                    entity = relationship(Table, foreign_keys=[pk_1_Table, ..., pk_n_Table], backref=backref(f'perm_{field}', uselist=False)) 
                """
                new_asso_name = f"ASSO_PERM_{tname.upper()}_{pdef.field.key.upper()}"
                columns = {
                    f"{pk}_{tname.lower()}": Column(f"{pk}_{tname.lower()}", primary_key=True)
                    for pk in table.pk()
                }
                rel_name = f"perm_{pdef.field.key.lower()}"
                fk_str = '[' + ",".join([f"{new_asso_name}.{key}" for key in columns.keys()]) + ']'

                columns['entity'] = relationship(
                    table,
                    lazy="select",
                    backref=backref(rel_name, uselist=False),
                    foreign_keys=fk_str,
                )
                columns['__table_args__'] = (
                    ForeignKeyConstraint(
                        [
                            f"{pk}_{tname.lower()}"
                            for pk in table.pk()
                        ],
                        [
                            f"{table.__tablename__}.{pk}"
                            for pk in table.pk()
                        ],
                    ),
                )
                for verb in enabled_verbs:
                    c = Column(ForeignKey("LISTGROUP.id"))
                    columns.update({f"id_{verb}": c})
                    columns.update({f"{verb}": relationship(ListGroup, lazy="select", foreign_keys=[c])})

                NewAsso = type(
                    new_asso_name,
                    (Base,), columns
                )

                # Setup svc.
                NewAsso.svc = CompositeEntityService(app=app, table=NewAsso)

                # Declare associated Marshmallow Schema:
                schema_columns = {
                    key: value
                    for key, value in table.ctrl.schema.declared_fields.items()
                    if key in table.pk()
                }
                for verb in enabled_verbs:
                    schema_columns.update({f"id_{verb}": ma.fields.Integer()})
                    schema_columns.update({f"{verb}": ma.fields.Nested("ListGroupSchema")})
                schema_columns['entity'] = ma.fields.Nested(table.ctrl.schema)

                NewAssoSchema = type(
                    f"AssoPerm{tname.capitalize()}{pdef.field.key.capitalize()}Schema",
                    (ma.Schema,),
                    schema_columns
                )

                # Set extra load field onto associated schema.
                # Load fields only -> permissions are not dumped.
                table.ctrl.schema.load_fields.update({rel_name: ma.fields.Nested(NewAssoSchema)})

                # Set up look up table for incomming requests.
                orig = table
                target = pdef.field.target.decl_class
                entry = {'table': NewAsso, 'from': [], 'verbs': enabled_verbs}

                def propagate(origin, target, entry):
                    """Propagates origin permissions on target permissions."""
                    entry['from'].append(origin)
                    lut[target] = lut.get(target, {'entries': []})  
                    lut[target]['entries'].append(entry)
                    if target.__name__ in cls._Base__permissions:
                        origin = target
                        for target_pdef in cls._Base__permissions[target.__name__][1]:
                            propagate(origin, target_pdef.field.target.decl_class, deepcopy(entry))

                propagate(orig, target, entry)
        cls._Base__permissions = lut

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate tablename."""
        return cls.__name__.upper()

    @classmethod
    def relationships(cls):
        """Return table relationships."""
        return inspect(cls).mapper.relationships

    @classmethod
    def target_table(cls, name):
        """Return target table of a property."""
        c = cls.col(name).property
        return c.target if isinstance(c, Relationship) else None

    @classmethod
    def pk(cls):
        """Return primary key names."""
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

    emited_at = Column(
        TIMESTAMP(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    validated_at = Column(TIMESTAMP(timezone=True))

@dataclass
class Permission:
    """Holds permissions for a given entity's attributes."""
    field: Column
    # Verbs.
    create: bool=False
    read: bool=False
    update: bool=False
    download: bool=False
    visualize: bool=False
    # verbs = [create, read, update, download, visualize]
    # Flags.
    # propagates: bool=True # ? 
    # use_same: bool=True
    # TODO: check inputs
    # def __init__(
    #     self,

    # ) -> None:
    #     pass

""""""
"""Class that produces necessary fields to declare ressource permissions for an entity.
    for each action in [CREATE, READ, UPDATE, DELETE, DOWNLOAD].
"""
# def __init_subclass__(cls, **kwargs) -> None:
#     """To restrict on some tables."""
#     if S3File in cls.__bases__:
#         cls.id_ls_download = declared_attr(cls.id_ls_download)
#         cls.ls_download = declared_attr(cls.ls_download)
#     super().__init_subclass__(**kwargs)

# @declared_attr
# def id_ls_download(_):
#     return Column(ForeignKey("LISTGROUP.id"), nullable=True)

# @declared_attr
# @classmethod
# def ls_download(cls) -> Mapped["ListGroup"]:
#     return relationship("ListGroup", foreign_keys=[cls.id_ls_download], lazy="select")

# @declared_attr
# def id_ls_create(_):
#     return Column(ForeignKey("LISTGROUP.id"), nullable=True)

# @declared_attr
# @classmethod
# def ls_create(cls) -> Mapped["ListGroup"]:
#     return relationship("ListGroup", foreign_keys=[cls.id_ls_create], lazy="select")

# @declared_attr
# def id_ls_read(_):
#     return Column(ForeignKey("LISTGROUP.id"), nullable=True)

# @declared_attr
# @classmethod
# def ls_read(cls) -> Mapped["ListGroup"]:
#     return relationship("ListGroup", foreign_keys=[cls.id_ls_read], lazy="select")

# @declared_attr
# def id_ls_update(_):
#     return Column(ForeignKey("LISTGROUP.id"), nullable=True)

# @declared_attr
# @classmethod
# def ls_update(cls) -> Mapped["ListGroup"]:
#     return relationship("ListGroup", foreign_keys=[cls.id_ls_update], lazy="select")

# @declared_attr
# def name_owner_group(_):
#     return Column(ForeignKey("GROUP.name"), nullable=True)

# @declared_attr
# @classmethod
# def owner_group(cls) -> Mapped["Group"]:
#     return relationship(foreign_keys=[cls.name_owner_group], lazy="select")
