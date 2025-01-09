from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, Integer, ForeignKey, Boolean, String, ForeignKeyConstraint, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.asyncio import AsyncSession

from biodm.components.table import Base, S3File#, Permission
from biodm.utils.security import Permission
# from .asso import asso_dataset_tag

if TYPE_CHECKING:
    from .dataset import Dataset


class File(S3File, Base):
    id              = Column(Integer,      primary_key=True)
    dataset_id      = Column(Integer,      nullable=False)
    dataset_version = Column(SmallInteger, nullable=False)

    # submitter_username:  Mapped[str] = mapped_column(ForeignKey("USER.username"), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["dataset_id", "dataset_version"],
            ["DATASET.id", "DATASET.version"],
            name="fk_file_dataset",
        ),
        UniqueConstraint(
            "filename",
            "extension",
            "dataset_id",
            "dataset_version",
            name="uc_file_in_dataset"
        )
    )

    @hybrid_property
    async def key(self) -> str:
        # Pop session, populated by S3Service just before asking for that attr.
        session: AsyncSession = self.__dict__.pop('session')
        await session.refresh(self, ['dataset', 'key_salt', 'filename', 'extension'])
        await session.refresh(self.dataset, ['project'])
        return (
            f"{self.key_salt}_{self.dataset.project.name}_{self.dataset.name}_"
            f"{self.filename}.{self.extension}"
        )

    # relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="files", foreign_keys=[dataset_id, dataset_version])

#     # dataset: Mapped["Dataset"] = relationship(back_populates="files", foreign_keys=[dataset_id, dataset_version])
#     # dataset: Mapped["Dataset"] = relationship('Dataset', primaryjoin="and_(Dataset.id == File.dataset_id, Dataset.version == File.dataset_version)")
#     #  foreign_keys=[dataset_id, dataset_version]

    # __permissions__ = (
    #     Permission("self", download=True),
    # )
