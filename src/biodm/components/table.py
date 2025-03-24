"""SQLAlchemy tables declarative parent classes
- Declarative Base
- S3File entity
- Versioned
"""
from copy import deepcopy
from typing import TYPE_CHECKING, Any, List, Self, Tuple, Type, Set, ClassVar, Type
from uuid import uuid4

from marshmallow.orderedset import OrderedSet
from sqlalchemy import (
    BOOLEAN, Integer, func, inspect, Column, String, TIMESTAMP, ForeignKey, BigInteger, select
)
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    DeclarativeBase, relationship, Relationship, mapped_column, Mapped, declared_attr,
    ONETOMANY, MANYTOONE, MANYTOMANY, make_transient, column_property, aliased
)

from biodm import config
from biodm.utils.sqla import get_max_id
from biodm.utils.utils import utcnow, classproperty


if TYPE_CHECKING:
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
    :param is_permission: Is permission table flag
    :type is_permission: bool
    :param last_max_id: Support non duplicate sqlite id population
    :type last_max_id: int
    """
    svc: ClassVar[Type['DatabaseService']]
    ctrl: ClassVar[Type['ResourceController']]
    is_permission: bool = False
    last_max_id: int=0

    def __init_subclass__(cls, **kw: Any) -> None:
        """Populates permission dict."""
        from biodm.utils.security import PermissionLookupTables
        if hasattr(cls, "__permissions__"):
            PermissionLookupTables.raw_permissions[cls.__name__] = (cls, cls.__permissions__)
        return super().__init_subclass__(**kw)

    @declared_attr
    def __tablename__(cls):
        """Generate tablename."""
        return cls.__name__.upper()

    @classmethod
    def dyn_relationships(cls):
        """Return table relationships. dyn stands for dynamic -> use for setup."""
        return inspect(cls).mapper.relationships

    @classproperty
    def relationships(cls):
        """Table relationships. Memoized result -> use for runtime."""
        return cls.dyn_relationships()

    @classmethod
    def target_table(cls, name):
        """Return target table of a property."""
        col = cls.col(name).property
        return col.target if isinstance(col, Relationship) else None

    @classproperty
    def pk(cls) -> OrderedSet[str]:
        """Return primary key names."""
        pks = [c.name for c in cls.__table__.primary_key.columns]
        if cls.is_versioned: # ensure version is last.
            pks.remove('version')
            pks.append('version')
        return OrderedSet(pks)

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
        # Enforced by DatabaseService.populate_ids_sqlite
        if name == 'id' and 'sqlite' in str(config.DATABASE_URL):
            return True

        if cls.__table__.columns[name] is cls.__table__.autoincrement_column:
            return True

        return cls.col(name).autoincrement == True

    @classmethod
    def has_default(cls, name: str) -> bool:
        """Flag if column has default value."""
        col = cls.col(name)
        return bool(col.default or col.server_default or cls.is_autoincrement(name))

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
                cls.has_default(c.name)
            )
        )

    @classproperty
    def has_submitter_username(cls) -> bool:
        """True if table has FK pointing to USER.username called 'submitter_username'

        :return: Flag
        :rtype: bool
        """
        return (
            'submitter_username' in cls.__dict__ and
            cls.submitter_username.foreign_keys  and
            len(cls.submitter_username.foreign_keys) == 1 and
            next(
                iter(
                    cls.submitter_username.foreign_keys
                )
            ).target_fullname == 'USER.username'
        )

    @classproperty
    def has_composite_pk_with_leading_id_sqlite(cls) -> bool:
        return (
            'sqlite' in str(config.DATABASE_URL) and
            hasattr(cls, 'id') and
            cls.pk.__len__() > 1
        )

    @staticmethod
    async def _realign_cloned_versioned_collections(
        src: List[Any],
        dst: List[Any],
        session: AsyncSession
    ):
        """Realigns cloned items primary keys during cloning of a versioned collection

        :param src: Source list
        :type src: List[Any]
        :param dst: Destination list
        :type dst: List[Any]
        :param session: session
        :type session: AsyncSession
        """
        to_realign = []
        skip = []
        pk_nover = src[0].pk - {'version'}

        for i, one in enumerate(src):
            if i in skip:
                continue

            entry = [i]
            for j, one_prime in enumerate(src[i+1:], i+1):
                if all([
                    getattr(one, k) == getattr(one_prime, k)
                    for k in pk_nover
                ]):
                    entry.append(j)
                    skip.append(j)

            if len(entry) > 1:
                to_realign.append(entry)

        if to_realign:
            await session.flush() # Generate ids
            for entry in to_realign:
                first = dst[entry[0]]
                for idx in entry[1::]:
                    for k in pk_nover:
                        setattr(dst[idx], k, getattr(first, k))

    def __deepcopy__(self, memo):
        """set deepcopy method to copy only the fields as copying relationships causes errors."""
        return self.__class__(**{
            f: deepcopy(getattr(self, f), memo)
            for f in self.__table__.columns.keys()
        })

    async def clone(
        self,
        session: AsyncSession,
        new_item: Self | None = None,
        updated_rels: List[str] | None = None
    ) -> Self:
        """Deep clone an entity with its relationships.

        :param session: session
        :type session: AsyncSession
        :param new_item: New instance, if None -> generated with make_transient, defaults to None
        :type new_item: Self | None, optional
        :param updated_rels: list of relationship to ignore while cloning, defaults to None
        :type updated_rels: List[str] | None, optional
        :raises NotImplementedError: canary, for versioned case of one-to-one
        :return: cloned item
        :rtype: Self
        """
        if not new_item: # May be set for top level call
            new_item = deepcopy(self)
            make_transient(new_item)

            # Delete defaultable pk parts and let flush regen
            for key in self.pk - {'version'}:
                if self.has_default(key):
                    delattr(new_item, key)

                # handle sqlite quirks
                if self.has_composite_pk_with_leading_id_sqlite:
                    max_id = await get_max_id(self, session=session)
                    if (max_id > self.__class__.last_max_id):
                        new_item.id = max_id+1
                    else:
                        new_item.id = self.__class__.last_max_id
                    self.__class__.last_max_id = new_item.id+1

        session.add(new_item)

        with session.no_autoflush:
            for key, rel in self.relationships.items():
                if key in (updated_rels or []):
                    continue # Overwritten by update

                if rel.direction is MANYTOONE and (not self.is_permission or key == 'entity'):
                    continue # Handled by copying local fks

                old_attached = await getattr(self.awaitable_attrs, key)
                if not old_attached:
                    continue # Nothing to clone
                await getattr(new_item.awaitable_attrs, key)

                if rel.direction is MANYTOONE and self.is_permission and key != 'entity':
                    # Do some extra cloning for permissions
                    # as we need ListGroups to be mutable for new entities
                    new_attached = await old_attached.clone(session=session)
                    setattr(new_item, 'id_' + key, None)
                    setattr(new_item, key, new_attached)

                elif rel.direction is MANYTOMANY:
                    new_collection = rel.collection_class(old_attached)
                    setattr(new_item, key, new_collection)

                elif rel.direction is ONETOMANY:
                    if rel.collection_class:
                        new_collection = rel.collection_class([
                            await one.clone(session=session)
                            for one in old_attached
                        ])
                        setattr(new_item, key, new_collection)

                        # Special versioned case, we might need to realign ids
                        if rel.mapper.entity.svc.table.is_versioned:
                            await self._realign_cloned_versioned_collections(
                                src=old_attached, dst=new_collection, session=session
                            )

                    else:
                        if rel.mapper.entity.svc.table.is_versioned:
                            # [canary]: should not happen but we'll be notified in case.
                            raise NotImplementedError

                        new_attached = await old_attached.clone(session=session)
                        setattr(new_item, key, new_attached)
        return new_item


class S3File:
    """Class to use in order to have a file managed on S3 bucket associated to this table
        Defaults internal fields that are expected by S3Service."""
    filename = Column(String(100), nullable=False)
    extension = Column(String(10), nullable=False)
    ready = Column(BOOLEAN, nullable=False, server_default='0')
    size = Column(BigInteger, nullable=False)

    upload_id: Mapped[int]         = mapped_column(ForeignKey("UPLOAD.id"),       nullable=True)

    @declared_attr
    def upload(cls) -> Mapped["Upload"]:
        return relationship(backref="file", foreign_keys=[cls.upload_id], lazy="joined")

    dl_count = Column(Integer, nullable=False, server_default='0')

    key_salt = Column(String, nullable=False, default=lambda: str(uuid4()))

    emited_at = Column(
        TIMESTAMP(timezone=True), default=utcnow, nullable=False
    )
    validated_at = Column(TIMESTAMP(timezone=True))

    @hybrid_property
    async def key(self) -> str:
        # Pop session, populated by S3Service just before asking for that attr.
        session: AsyncSession = self.__dict__.pop('session')
        key_fields = ['key_salt', 'filename', 'extension']
        if self.is_versioned:
            key_fields += ['version']

        await session.refresh(self, key_fields)

        version = "_v" + str(self.version) if self.svc.table.is_versioned else ""
        return f"{self.key_salt}_{self.filename}{version}.{self.extension}"


class Versioned:
    """Versioned entity parent class.

    - Populates version as primary_key column
    - Disable /update, enable /release
    """
    version = Column(Integer, server_default='1', nullable=False, primary_key=True)


def add_versioned_table_methods() -> None:
    """Called after tables initialization to have access to aliased
        which is not the case during initialization."""
    for table in set(Base._sa_registry.mappers):
        decl_class = table.entity
        if issubclass(decl_class, Versioned) and not hasattr(decl_class, 'is_latest'):
            # is_latest - flag
            alias = aliased(decl_class)
            agg = [k for k in decl_class.pk if k != 'version']

            inspect(decl_class).add_property(
                "is_latest",
                column_property(
                    decl_class.version == (
                        select(func.max(alias.version))
                        .where(*[getattr(alias, k) == getattr(decl_class, k) for k in agg])
                        .group_by(*[getattr(alias, k) for k in agg])
                    ).scalar_subquery()
                )
            )
            # TODO: prev/next versions ?
