"""SQLAlchemy tables convenience Parent classes:
- Declarative Base
- File entity
- Permission setup logic
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from inspect import getmembers, ismethod
from typing import TYPE_CHECKING, Any, List, Dict, Tuple, Type, Set, ClassVar, Type, Self
from uuid import uuid4

import marshmallow as ma
from sqlalchemy import (
    BOOLEAN, ForeignKeyConstraint, Integer, UniqueConstraint, Uuid, inspect, Column, String, TIMESTAMP, ForeignKey,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    DeclarativeBase, relationship, Relationship, backref, ONETOMANY, mapped_column, MappedColumn, Mapped, make_transient, column_property, declared_attr
)
from sqlalchemy.ext.asyncio import AsyncSession

from biodm import config
from biodm.exceptions import ImplementionError
from biodm.utils.utils import utcnow, classproperty

if TYPE_CHECKING:
    from biodm import Api
    from biodm.components.services import DatabaseService
    from biodm.components.controllers import ResourceController
    from sqlalchemy.orm import Relationship
    from biodm.tables import Upload


class Base(DeclarativeBase, AsyncAttrs):
    """Base class for ORM declarative Tables.
 
    :param svc: Enable entity - service linkage
    :type svc: DatabaseService
    :param ctrl: Enable entity - controller linkage -> Resources tables only
    :type ctrl: ResourceController
    :param raw_permissions: Store rules for user defined permissions on hierarchical entities
    :type raw_permissions: Dict
    :param permissions: Store processed permissions with hierarchical linkage info
    :type permissions: Dict
    :param login_required: Handle @login_required nested cases (create, read_nested)
    :type login_required: Dict
    :param group_required: Handle @group_required nested cases (create, read_nested)
    :type group_required: Dict
    """
    svc: ClassVar[Type[DatabaseService]]
    ctrl: ClassVar[Type[ResourceController]]

    raw_permissions: ClassVar[Dict[str, Tuple[Type[Self], Tuple[Permission]]]] = {}
    permissions: ClassVar[Dict[Type[Self], Any]] = {}
    login_required: ClassVar[Dict[Type[Self], Any]] = {}
    group_required: ClassVar[Dict[Type[Self], Any]] = {}

    def __init_subclass__(cls, **kw: Any) -> None:
        """Populates permission dict in a first pass."""
        if hasattr(cls, "__permissions__"):
            Base.raw_permissions[cls.__name__] = (cls, cls.__permissions__)
        return super().__init_subclass__(**kw)

    @staticmethod
    def _gen_perm_table(app: Api, table: Type[Base], field: Column, verbs: List[str]):
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
        :return: name of backref-ed attribute, permission table.
        :rtype: Tuple[str, Base]
        """
        # Defered imports as they depend on this module.
        from biodm.components.services import CompositeEntityService
        from biodm.tables import ListGroup

        new_asso_name = f"ASSO_PERM_{table.__name__.upper()}_{field.key.upper()}"
        rel_name = f"perm_{field.key.lower()}"

        columns: Dict[str, Column[Any] | MappedColumn[Any] | Relationship | Tuple[Any]] = {
            f"{pk}_{table.__name__.lower()}": Column(primary_key=True)
            for pk in table.pk
        }
        columns['entity'] = relationship(
            table,
            backref=backref(
                rel_name,
                uselist=False,
                cascade="all, delete-orphan" # important.
            ),
            foreign_keys="[" + ",".join(
                [
                    f"{new_asso_name}.{key}"
                    for key in columns.keys()
                ]
            ) + "]",
            passive_deletes=True,
            single_parent=True, # also.
        )
        columns['__table_args__'] = (
            ForeignKeyConstraint(
                [
                    f"{pk}_{table.__name__.lower()}"
                    for pk in table.pk
                ],
                [
                    f"{table.__tablename__}.{pk}"
                    for pk in table.pk
                ],
            ),
        )
        for verb in verbs:
            c = mapped_column(ForeignKey("LISTGROUP.id"))
            columns.update(
                {
                    f"id_{verb}": c,
                    f"{verb}": relationship(ListGroup, foreign_keys=[c])
                }
            )

        # Declare table and setup svc.
        NewAsso = type(new_asso_name, (Base,), columns)
        setattr(NewAsso, 'svc', CompositeEntityService(app=app, table=NewAsso))

        return rel_name, NewAsso

    @staticmethod
    def _gen_perm_schema(table: Type[Base], field: Column, verbs: List[str]):
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
            if key in table.pk
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
        lut: Dict[Base, List[Dict[str, Any]]],
        origin: Type[Base],
        target: Type[Base],
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

        target_perms = Base.permissions.get(target.__name__, ('', []))[1]
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

        Has to be done after all tables have been declared.

        Currently assumes straight composition:
        i.e. You cannot flag an o2m with the same target in two different parent classes.
        """
        lut = {}
        for table, permissions in Base.raw_permissions.values():
            for perm in permissions:
                if perm.field.direction is not ONETOMANY:
                    raise ImplementionError(
                        "Permission should only be applied on One-to-Many relationships fields "
                        "A.K.A 'composition' pattern."
                    )
                verbs = perm.enabled_verbs
                if not verbs:
                    continue

                # Declare permission table and associated schema.
                rel_name, NewAsso = cls._gen_perm_table(app, table, perm.field, verbs)
                NewAssoSchema = cls._gen_perm_schema(table, perm.field, verbs)

                # Set extra load field onto associated schema.
                # Load fields only -> permissions are not dumped.
                table.ctrl.schema.load_fields.update(
                    {rel_name: ma.fields.Nested(NewAssoSchema)}
                )

                # Set up look up table for incomming requests.
                entry = {'table': NewAsso, 'from': [], 'verbs': verbs}
                cls._propagate_perm(
                    lut=lut,
                    origin=table,
                    target=perm.field.target.decl_class,
                    entry=entry
                )
        Base.permissions = lut

        # Check if methods have those attributes set for [login|group]_required nested cases.
        for controller in app.controllers:
            for func in [f for _, f in getmembers(controller, predicate=ismethod)]:
                if hasattr(func, 'login_required'):
                    Base.login_required[controller.table] = (
                        Base.login_required.get(controller.table, [])
                    )
                    Base.login_required[controller.table].append(func.login_required)
                if hasattr(func, 'group_required'):
                    Base.group_required[controller.table] = (
                        Base.group_required.get(controller.table, {})
                    )
                    Base.group_required[controller.table].update(func.group_required)

    @declared_attr
    def __tablename__(cls):
        """Generate tablename."""
        return cls.__name__.upper()

    @classmethod
    def relationships(cls):
        """Return table relationships."""
        return inspect(cls).mapper.relationships

    @classmethod
    def target_table(cls, name):
        """Return target table of a property."""
        col = cls.col(name).property
        return col.target if isinstance(col, Relationship) else None

    @classproperty
    def pk(cls) -> Set[str]:
        """Return primary key names."""
        return set(
            str(pk).rsplit('.', maxsplit=1)[-1]
            for pk in cls.__table__.primary_key.columns
        )

    @classmethod
    def col(cls, name: str):
        """Return columns object from name."""
        return cls.__dict__[name]

    @classmethod
    def is_autoincrement(cls, name: str) -> bool:
        """Flag if column is autoincrement.

        Warning! This check is backend dependent and should be changed when supporting a new one.
        E.g. Oracle backend will not react appropriately.
        - https://groups.google.com/g/sqlalchemy/c/o5YQNH5UUko
        """
        if name == 'id' and 'sqlite' in config.DATABASE_URL:
            return True

        if cls.__table__.columns[name] is cls.__table__.autoincrement_column:
            return True

        return cls.col(name).autoincrement == True

    @classmethod
    def has_default(cls, name: str) -> bool:
        """Flag if column has default value."""
        col = cls.col(name)
        return col.default or col.server_default

    @classmethod
    def colinfo(cls, name: str) -> Tuple[Column, type]:
        """Return column and associated python type for conditions."""
        col = cls.col(name)
        return col, col.type.python_type

    @classproperty
    def is_versioned(cls) -> bool:
        return issubclass(cls, Versioned)

    @classproperty
    def required(cls) -> Set[str]:
        """Gets all required fields to create a new entry in this table.

        :return: fields name list
        :rtype: Set[str]
        """
        return set(
            c.name for c in cls.__table__.columns
            if not (
                c.nullable or
                cls.has_default(c.name) or
                cls.is_autoincrement(c.name)
            )
        )


class S3File:
    """Class to use in order to have a file managed on S3 bucket associated to this table
        Defaults internal fields that are expected by S3Service."""
    filename = Column(String(100), nullable=False)
    extension = Column(String(10), nullable=False)
    ready = Column(BOOLEAN, nullable=False, server_default='0')
    size = Column(Integer, nullable=False)

    # upload_form = Column(String(2000)) # , nullable=False+
    id_upload: Mapped[int]         = mapped_column(ForeignKey("UPLOAD.id"),       nullable=True)

    @declared_attr
    def upload(cls) -> Mapped["Upload"]:
        return relationship(backref="file", foreign_keys=[cls.id_upload])

    dl_count = Column(Integer, nullable=False, server_default='0')

    key_salt = Column(String, nullable=False, default=lambda: str(uuid4()))

    emited_at = Column(
        TIMESTAMP(timezone=True), default=utcnow, nullable=False
    )
    validated_at = Column(TIMESTAMP(timezone=True))


@dataclass
class Permission:
    """Holds permissions for a given entity's attributes."""
    field: Column
    # Verbs.
    read: bool=False
    write: bool=False
    download: bool=False

    @classproperty
    def fields(cls) -> Set[str]:
        return set(cls.__dataclass_fields__.keys() - 'fields')

    @property
    def enabled_verbs(self) -> Set[str]:
        return set(
            verb
            for verb, enabled in self.__dict__.items()
            if enabled and verb != 'field'
        )


class Versioned:
    """Versioned entity parent class.

    - Populates version as primary_key column
    - Disable /update, enable /release
    """
    version = Column(Integer, server_default='1', nullable=False, primary_key=True)

    # def new_version(self, session):
    #     # expire parent's reference to us
    #     session.expire(self.parent, ["child"])

    #     # create new version
    #     Versioned.new_version(self, session)

    #     # re-add ourselves to the parent.  this causes the
    #     # parent foreign key to be updated also
    #     self.parent.child = self

        #     -> Update parent(s).
        #     -> Adopt children(s)

    # TODO:
    # - Set next_version/prev_version relationships. 
