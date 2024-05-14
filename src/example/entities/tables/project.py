from typing import TYPE_CHECKING, List

from sqlalchemy import CHAR, TIMESTAMP, Column, Integer, ForeignKey, Boolean, String, ForeignKeyConstraint, SmallInteger, text
from sqlalchemy.orm import Mapped, relationship
from biodm.components.table import Base, S3File, Permission
# from .asso import asso_dataset_tag

if TYPE_CHECKING:
    from .dataset import Dataset


class Project(Base):
    id = Column(Integer, nullable=False, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(String, nullable=True)

    # created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    # updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))

    # relationships
    datasets: Mapped[List["Dataset"]] = relationship(back_populates="project")
    # analyses: Mapped[List["Analysis"]] = relationship(back_populates="project")

    # id_user_principal_investigator = Column(Integer, nullable=False)
    # id_user_updater = Column(Integer, nullable=False)
    # id_user_responsible = Column(Integer, nullable=False)

    __permissions__ = {
        'datasets': Permission(datasets, create=True, read=True, update=True)
    }
