from typing import List, TYPE_CHECKING

from sqlalchemy.orm import mapped_column, Mapped, relationship

from biodm.components import Base

if TYPE_CHECKING:
    from .upload_part import UploadPart


class Upload(Base):
    id: Mapped[int]                   = mapped_column(primary_key=True)
    s3_uploadId: Mapped[str]          = mapped_column(nullable=True)
    parts: Mapped[List["UploadPart"]] = relationship(
        back_populates="upload",
        lazy=False,
        cascade="save-update, merge, delete, expunge, delete-orphan",
    )
