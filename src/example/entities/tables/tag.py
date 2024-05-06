from typing import TYPE_CHECKING, List

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, relationship

from biodm.components.table import Base
from .asso import asso_dataset_tag

if TYPE_CHECKING:
    from .dataset import Dataset


class Tag(Base):
    id = Column(Integer, nullable=False, primary_key=True)
    name = Column(String, nullable=False) # primary_key=True

    # relationships
    # datasets: Mapped[List["Dataset"]] = relationship(
    #     secondary=asso_dataset_tag, 
    #     back_populates="tags"
    # )
