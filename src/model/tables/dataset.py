from typing import TYPE_CHECKING, List # Optional, 

from sqlalchemy import Column, Integer, SmallInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, relationship

from ..table import Base
from .asso import asso_dataset_tag
if TYPE_CHECKING:
    from .group import Group
    from .user import User
    from .tag import Tag


class Dataset(Base):
    # pk
    id:          Mapped[int] = Column(Integer,      primary_key=True, autoincrement=True)
    version:     Mapped[int] = Column(SmallInteger, primary_key=True, server_default='1')

    # data fields
    name:        Mapped[str] = Column(String(50), nullable=False)
    # description: Mapped[str] = Column(TEXT,       nullable=True)
    # created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    # updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    # permission_level = Column(CHAR(1),            nullable=False, server_default='3')
    # licence_s3_path = Column(String(100),         nullable=True)

    # # bio specific fields
    # specie =            Column(String(50),    nullable=False)
    # disease =           Column(String(50),    nullable=False)
    # treatment =         Column(String(50),    nullable=False)
    # genome_assembly =   Column(String(50),    nullable=False)
    # genome_annotation = Column(String(50),    nullable=False)
    # sample_type =       Column(String(50),    nullable=False)
    # sample_details =    Column(TEXT,          nullable=True)
    # sample_count =      Column(Integer,       nullable=False, server_default='0')
    # molecular_info =    Column(String(100),   nullable=False)
    # data_type =         Column(String(50),    nullable=False)
    # value_type =        Column(String(50),    nullable=False)
    # platform_name =     Column(String(50),    nullable=False)
    # platform_kit =      Column(String(50),    nullable=True)

    # supplementary_metadata = Column(JSONB, nullable=True)

    # Foreign keys
    name_group:      Mapped[int] = Column(ForeignKey("GROUP.name"), nullable=False)
    id_user_contact: Mapped[int] = Column(ForeignKey("USER.id"),    nullable=False)
    # id_project:      Mapped[int] = Column(ForeignKey("PROJECT.id"), nullable=False)

    # relationships
    # group:   Mapped["Group"] = relationship(back_populates="datasets")  
    # project: Mapped[Project]       = relationship(back_populates="datasets")
    contact: Mapped["User"]  = relationship(foreign_keys=[id_user_contact])
    # tags:    Mapped[List["Tag"]]     = relationship(
    #     secondary=asso_dataset_tag, 
    #     back_populates="datasets"
    # )
    # files:   Mapped[List["File"]]  = relationship(back_populates="dataset") 
    # permission_lv2: Mapped["Permission_lv2"] = relationship()

    # For Inheritance
    # discriminator = Column('type', String(20))
    # __mapper_args__ = {'polymorphic_on': discriminator}
