"""SQLAlchemy tables declarative parent classes
- Declarative Base
- S3File entity
- Versioned
"""
from typing import TYPE_CHECKING, Any, Tuple, Type, Set, ClassVar, Type, Dict
from uuid import uuid4

from sqlalchemy import (
    BOOLEAN, Integer, inspect, Column, String, TIMESTAMP, ForeignKey, BigInteger
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import (
    DeclarativeBase, relationship, Relationship, mapped_column, Mapped, declared_attr
)

from biodm import config
from biodm.utils.utils import utcnow, classproperty, OrderedSet


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
    """
    svc: ClassVar[Type['DatabaseService']]
    ctrl: ClassVar[Type['ResourceController']]

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


class S3File:
    """Class to use in order to have a file managed on S3 bucket associated to this table
        Defaults internal fields that are expected by S3Service."""
    filename = Column(String(100), nullable=False)
    extension = Column(String(10), nullable=False)
    ready = Column(BOOLEAN, nullable=False, server_default='0')
    size = Column(BigInteger, nullable=False)

    # upload_form = Column(String(2000)) # , nullable=False+
    upload_id: Mapped[int]         = mapped_column(ForeignKey("UPLOAD.id"),       nullable=True)

    @declared_attr
    def upload(cls) -> Mapped["Upload"]:
        return relationship(backref="file", foreign_keys=[cls.upload_id])

    dl_count = Column(Integer, nullable=False, server_default='0')

    key_salt = Column(String, nullable=False, default=lambda: str(uuid4()))

    emited_at = Column(
        TIMESTAMP(timezone=True), default=utcnow, nullable=False
    )
    validated_at = Column(TIMESTAMP(timezone=True))


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
