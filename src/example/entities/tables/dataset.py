from typing import List, Set # Optional, 

from sqlalchemy import BIGINT, text, func, Column, Identity, Integer, Sequence, SmallInteger, ForeignKey, String, PrimaryKeyConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship, mapped_column

from biodm.components.table import Base, Versioned
from biodm.tables import Group, User
from biodm import config
from biodm.utils.security import Permission

from .asso import asso_dataset_tag
from .file import File
from .tag import Tag
from .project import Project


class Dataset(Versioned, Base):
    id = Column(Integer, primary_key=True, autoincrement=not 'sqlite' in config.DATABASE_URL)
    # data fields
    name:        Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text,       nullable=True)
    # # created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=)datetime.datetime.utcnow
    # # updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=)
    # # licence_s3_path = Column(String(100),         nullable=True)

    # # # bio specific fields
    # # specie =            Column(String(50),    nullable=False)
    # # disease =           Column(String(50),    nullable=False)
    # # treatment =         Column(String(50),    nullable=False)
    # # genome_assembly =   Column(String(50),    nullable=False)
    # # genome_annotation = Column(String(50),    nullable=False)
    # # sample_type =       Column(String(50),    nullable=False)
    # # sample_details =    Column(TEXT,          nullable=True)
    # # sample_count =      Column(Integer,       nullable=False, server_default='0')
    # # molecular_info =    Column(String(100),   nullable=False)
    # # data_type =         Column(String(50),    nullable=False)
    # # value_type =        Column(String(50),    nullable=False)
    # # platform_name =     Column(String(50),    nullable=False)
    # # platform_kit =      Column(String(50),    nullable=True)

    # # supplementary_metadata = Column(JSONB, nullable=True)

    # # Foreign keys
    contact_username: Mapped[str]  = mapped_column(ForeignKey("USER.username"),    nullable=False)
    project_id:       Mapped[int]  = mapped_column(ForeignKey("PROJECT.id"),       nullable=False)

    # # relationships
    # policy - cascade="save-update, merge" ?
    contact: Mapped["User"]       = relationship(foreign_keys=[contact_username])
    tags:    Mapped[Set["Tag"]]   = relationship(secondary=asso_dataset_tag, uselist=True)
    project: Mapped["Project"]    = relationship(back_populates="datasets")
    files:   Mapped[List["File"]] = relationship(back_populates="dataset")

    # # permission_lv2: Mapped["Permission_lv2"] = relationship()

    # # For Inheritance
    # # discriminator = Column('type', String(20))
    # # __mapper_args__ = {'polymorphic_on': discriminator}
    # __table_args__ = (
    #     # UniqueConstraint('id', 'version', name='uc_pk_dataset'),
    #     PrimaryKeyConstraint('id', 'version', name='pk_dataset'),
    # )

    #  Special parameters.
    __permissions__ = (
        Permission(files, read=True, write=True, download=True),
    )
