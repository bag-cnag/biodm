from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, ForeignKey, Boolean, String, ForeignKeyConstraint, SmallInteger
from sqlalchemy.orm import Mapped, relationship
from core.components.table import Base
# from .asso import asso_dataset_tag
if TYPE_CHECKING:
    from .dataset import Dataset


class File(Base):
    id = Column(Integer, nullable=False, primary_key=True)
    filename = Column(String(100), nullable=False)
    url = Column(String(200), nullable=False)
    ready = Column(Boolean, nullable=False, server_default='FALSE')

#     # id_dataset      = Column(ForeignKey("DATASET.id"), nullable=False)
#     # version_dataset = Column(ForeignKey("DATASET.version"), nullable=False)
    id_dataset = Column(Integer, nullable=False)
    version_dataset = Column(SmallInteger, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["id_dataset", "version_dataset"],
            ["DATASET.id", "DATASET.version"],
            name="fk_file_dataset",
        ),
    )

    # relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="files", foreign_keys=[id_dataset, version_dataset])

#     # dataset: Mapped["Dataset"] = relationship(back_populates="files", foreign_keys=[id_dataset, version_dataset])
#     # dataset: Mapped["Dataset"] = relationship('Dataset', primaryjoin="and_(Dataset.id == File.id_dataset, Dataset.version == File.version_dataset)")
#     #  foreign_keys=[id_dataset, version_dataset]