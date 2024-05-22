from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Dict
import datetime

import marshmallow as ma
from sqlalchemy import (
    ForeignKeyConstraint, inspect, Column,
    Integer, String, TIMESTAMP, ForeignKey,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, Relationship, backref, ONETOMANY

from biodm.exceptions import ImplementionError

if TYPE_CHECKING:
    from biodm import Api
    from biodm.tables import User
    from biodm.components.services import DatabaseService
    from biodm.components.controllers import ResourceController


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
        """Populates permission dict in a first pass."""
        if hasattr(cls, "__permissions__"):
            cls._Base__permissions[cls.__name__] = (cls, cls.__permissions__)
        return super().__init_subclass__(**kw)

    @staticmethod
    def _gen_perm_table(app: Api, table: Base, field: Column, verbs: List[str]):
        """Declare new associative table for a given permission:
        This Associative table uses a one-to-one relationship pattern to backref a field
        perm_{field} that holds permissions informations __without touching at Parent table
        definition__.

        The syntax is a little convoluted because most tools don't hanlde properly composite
        primary keys. However, the following nicely does the trick.

        This below achieves the following:
        class ASSO_PERM_{TABLE}_{FIELD}(Base):
            pk_1_Table = Column(ForeignKey("TABLE".{pk_1}), primary_key=True)
            ...
            pk_n_Table = ...

            entity = relationship(
                Table, 
                foreign_keys=[pk_1_Table, ..., pk_n_Table],
                backref=backref(f'perm_{field}', uselist=False)
            ) 

        :param app: Api object, used to declare service.
        :type app: Api
        :param table: Table object
        :type table: Base
        :param field: many-to-one Relationship field
        :type field: Column
        :param verbs: enabled verbs
        :type verbs: List[str]
        :return: name of permission relationship that gets populated into table and the new associative table.
        :rtype: Tuple[str, Base]
        """
        # Defered imports as they depend on this module.
        from biodm.components.services import CompositeEntityService
        from biodm.tables import ListGroup

        new_asso_name = f"ASSO_PERM_{table.__name__.upper()}_{field.key.upper()}"
        rel_name = f"perm_{field.key.lower()}"

        columns = {
            f"{pk}_{table.__name__.lower()}": Column(primary_key=True)
            for pk in table.pk()
        }
        columns['entity'] = relationship(
            table,
            backref=backref(rel_name, uselist=False),
            foreign_keys="[" + ",".join(
                [
                    f"{new_asso_name}.{key}"
                    for key in columns.keys()
                ]   
            ) + "]",
            passive_deletes=True
        )
        columns['__table_args__'] = (
            ForeignKeyConstraint(
                [
                    f"{pk}_{table.__name__.lower()}"
                    for pk in table.pk()
                ],
                [
                    f"{table.__tablename__}.{pk}"
                    for pk in table.pk()
                ],
            ),
        )
        for verb in verbs:
            c = Column(ForeignKey("LISTGROUP.id"))
            columns.update(
                {
                    f"id_{verb}": c,
                    f"{verb}": relationship(ListGroup, foreign_keys=[c])
                }
            )

        # Declare table.
        NewAsso = type(
            new_asso_name,
            (Base,), columns
        )

        # Setup svc.
        NewAsso.svc = CompositeEntityService(app=app, table=NewAsso)

        return rel_name, NewAsso

    @staticmethod
    def _gen_perm_schema(table: Base, field: Column, verbs: List[str]):
        """Generates permission schema for a permission table. 

        :param table: Table object
        :type table: Base
        :param field: many-to-one Relationship field
        :type field: Column
        :param verbs: enabled verbs
        :type verbs: List[str]
        :return: permission schema
        :rtype: ma.Schema
        """
        # Copy primary key columns from original table schema.
        schema_columns = {
            key: value
            for key, value in table.ctrl.schema.declared_fields.items()
            if key in table.pk()
        }
        for verb in verbs:
            schema_columns.update(
                {
                    f"id_{verb}": ma.fields.Integer(),
                    f"{verb}": ma.fields.Nested("ListGroupSchema"),
                }
            )
        schema_columns['entity'] = ma.fields.Nested(table.ctrl.schema)

        return type(
            f"AssoPerm{table.__name__.capitalize()}{field.key.capitalize()}Schema",
            (ma.Schema,),
            schema_columns
        )

    @classmethod
    def _propagate_perm(
        cls,
        lut: Dict[str, List[Dict[str, Any]]],
        origin: Base,
        target: Base,
        entry: Dict[str, Any]
    ) -> None:
        """Propagates origin permissions on target permissions.
        -> Recursive BFS style.

        :param lut: lookup table to populate.
        :type lut: Dict[str, List[Dict[str, Any]]]
        :param origin: Origin table
        :type origin: Base
        :param target: Target table
        :type target: Base
        :param entry: Permission entry
        :type entry: Dict[str, Any]
        """
        entry['from'].append(origin)
        lut[target] = lut.get(target, [])
        lut[target].append(entry)

        target_perms = cls._Base__permissions.get(target.__name__, ('', []))[1]
        for perm in target_perms:
            cls._propagate_perm(lut, target, perm.field.target.decl_class, deepcopy(entry))

    @classmethod
    def setup_permissions(cls, app):
        """After tables have been added to Base, and before you initialize DB
        you shall call this method to factor in changes.

        - For each declared permission.
            - Creates an associative table
                - indexed by Parent table pk
                    - children hold parent id
                - holds listgroup objects mapped to enabled verbs
            - Set ref for Children controller
        -- Has to be done after all tables have been declared. --

        Currently assumes straight composition.
        i.e. You cannot flag an o2m with the same target in two different parent classes.
        """
        lut = {}
        for table, permissions in cls._Base__permissions.values():
            for perm in permissions:
                if perm.field.direction is not ONETOMANY:
                    raise ImplementionError(
                        "Permission should only be applied on one-to-many relationships fields. "
                        "A.K.A 'composition' pattern"
                    )
                verbs = perm.enabled_verbs()
                if verbs:
                    # Declare permission table and associated schema.
                    rel_name, NewAsso = cls._gen_perm_table(app, table, perm.field, verbs)
                    NewAssoSchema = cls._gen_perm_schema(table, perm.field, verbs)

                    # Set extra load field onto associated schema.
                    # Load fields only -> permissions are not dumped.
                    table.ctrl.schema.load_fields.update({rel_name: ma.fields.Nested(NewAssoSchema)})

                    # Set up look up table for incomming requests.
                    entry = {'table': NewAsso, 'from': [], 'verbs': verbs}
                    cls._propagate_perm(
                        lut=lut,
                        origin=table,
                        target=perm.field.target.decl_class,
                        entry=entry
                    )
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

    def enabled_verbs(self):
        return [
            verb
            for verb, enabled in self.__dict__.items()
            if enabled and verb != 'field'
        ]

    # verbs = [create, read, update, download, visualize]
    # Flags.
    # propagates: bool=True # ? 
    # use_same: bool=True
    # TODO: check inputs
    # def __init__(
    #     self,
