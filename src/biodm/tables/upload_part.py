from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship

from biodm.components import Base

if TYPE_CHECKING:
    from .upload import Upload

class UploadPart(Base):
    id_upload:   Mapped[int]      = mapped_column(ForeignKey("UPLOAD.id"), primary_key=True)
    part_number: Mapped[int]      = mapped_column(server_default='0', primary_key=True)
    form:        Mapped[str]      = mapped_column(nullable=False)
    # etag:        Mapped[str]      = mapped_column(nullable=True)
    upload:      Mapped["Upload"] = relationship(
                                        back_populates="parts",
                                        foreign_keys=[id_upload],
                                        single_parent=True
                                    )
