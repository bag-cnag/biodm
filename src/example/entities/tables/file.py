from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, Integer, ForeignKey, Boolean, String, ForeignKeyConstraint, SmallInteger
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.asyncio import AsyncSession

from biodm.components.table import Base, S3File#, Permission
from biodm.utils.security import Permission
# from .asso import asso_dataset_tag

if TYPE_CHECKING:
    from .dataset import Dataset


class File(S3File, Base):
    id = Column(Integer, nullable=False, primary_key=True)
    id_dataset = Column(Integer, nullable=False)
    version_dataset = Column(SmallInteger, nullable=False)

    # submitter_username:  Mapped[str] = mapped_column(ForeignKey("USER.username"), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["id_dataset", "version_dataset"],
            ["DATASET.id", "DATASET.version"],
            name="fk_file_dataset",
        ),
    )

    @hybrid_property
    async def key_salt(self) -> str:
        # Pop session, populated by S3Service just before asking for that attr.
        session: AsyncSession = self.__dict__.pop('session')
        await session.refresh(self, ['dataset'])
        await session.refresh(self.dataset, ['project'])
        return f"{self.dataset.project.name}_{self.dataset.name}"

    # relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="files", foreign_keys=[id_dataset, version_dataset])

#     # dataset: Mapped["Dataset"] = relationship(back_populates="files", foreign_keys=[id_dataset, version_dataset])
#     # dataset: Mapped["Dataset"] = relationship('Dataset', primaryjoin="and_(Dataset.id == File.id_dataset, Dataset.version == File.version_dataset)")
#     #  foreign_keys=[id_dataset, version_dataset]
