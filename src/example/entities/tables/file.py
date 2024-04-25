from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, ForeignKey, Boolean, String, ForeignKeyConstraint, SmallInteger
from sqlalchemy.orm import Mapped, relationship
from biodm.components.table import Base, S3File, Permission
# from .asso import asso_dataset_tag

if TYPE_CHECKING:
    from .dataset import Dataset


class File(Permission, S3File, Base):
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