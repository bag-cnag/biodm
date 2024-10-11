from typing import TYPE_CHECKING, List

from sqlalchemy import CHAR, TIMESTAMP, Column, Integer, ForeignKey, Boolean, String, ForeignKeyConstraint, SmallInteger, text
from sqlalchemy.orm import Mapped, relationship
from biodm.components.table import Base # S3File #, Permission
# from .asso import asso_dataset_tag
from biodm.utils.security import Permission


if TYPE_CHECKING:
    from .dataset import Dataset
    from .visualization import Visualization


class Project(Base):
    id          = Column(Integer,    primary_key=True)
    name        = Column(String(50), nullable=False)
    description = Column(String,     nullable=True)

    # created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    # updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))

    # relationshipsNoneNone
    datasets: Mapped[List["Dataset"]] = relationship(back_populates="project")
    # visualizations: Mapped[List["Visualization"]] = relationship(back_populates="project")
    # analyses: Mapped[List["Analysis"]] = relationship(back_populates="project")

    # id_user_principal_investigator = Column(Integer, nullable=False)
    # id_user_updater = Column(Integer, nullable=False)
    # id_user_responsible = Column(Integer, nullable=False)

    __permissions__ = (
        Permission(datasets, read=True, write=True, download=True, propagates_to=["files"]),
        #  propagates_to=[]
        # Permission("datasets.files", read=True, write=True, download=True),
        # Permission(visualizations, write=True)
    )
