from typing import List, Set # Optional, 

from sqlalchemy import Column, Identity, Integer, SmallInteger, ForeignKey, String, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from biodm.components.table import Base, Permission
from biodm.tables import Group, User
from .asso import asso_dataset_tag
from .file import File
from .tag import Tag
from .project import Project


class Dataset(Base):
    # pk
    ## For PostgresSQL
    id:          Mapped[int] = Column(Integer, autoincrement=True)
    version:     Mapped[int] = Column(SmallInteger, server_default='1')

    ## For sqlite
    # # TODO: test, document that composite pk are not well supported for sqlite.
    # id = Column(Integer, server_default='1')
    # version:     Mapped[int] = Column(SmallInteger, server_default='1')

    # data fields
    name:        Mapped[str] = Column(String(50), nullable=False)
    # # description: Mapped[str] = Column(TEXT,       nullable=True)
    # # created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))datetime.datetime.utcnow
    # # updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    # # permission_level = Column(CHAR(1),            nullable=False, server_default='3')
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
    username_user_contact: Mapped[int] = Column(ForeignKey("USER.username"),    nullable=False)
    id_project:      Mapped[int] = Column(ForeignKey("PROJECT.id"), nullable=False)

    # # relationships
    # policy - cascade="save-update, merge" ?
    contact: Mapped["User"]       = relationship(foreign_keys=[username_user_contact], lazy="select")
    tags:    Mapped[Set["Tag"]]   = relationship(secondary=asso_dataset_tag, uselist=True, lazy="select")
    project: Mapped["Project"]    = relationship(back_populates="datasets")
    files:   Mapped[List["File"]] = relationship(back_populates="dataset", lazy="select")

    # # permission_lv2: Mapped["Permission_lv2"] = relationship()

    # # For Inheritance
    # # discriminator = Column('type', String(20))
    # # __mapper_args__ = {'polymorphic_on': discriminator}
    # __table_args__ = (
    #     # UniqueConstraint('id', 'version', name='uc_pk_dataset'),
    #     PrimaryKeyConstraint('id', 'version', name='pk_dataset'),
    # )

    __permissions__ = {
        # Flag many-to-entity (composition pattern) with permissions. 
        "files": Permission(files, create=True, visualize=True)
    }

    __table_args__ = (
        PrimaryKeyConstraint(id, version),
    )
