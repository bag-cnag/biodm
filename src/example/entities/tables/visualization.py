from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, relationship, mapped_column

from biodm.components.table import Base

if TYPE_CHECKING:
    from biodm.tables import User
    # from .project import Project
    from .file import File

class Visualization(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=True)

    # Foreign Keys
    user_username:   Mapped[str] = mapped_column(ForeignKey("USER.username"))
    # project_id:      Mapped[int] = mapped_column(ForeignKey("PROJECT.id"))
    id_file:         Mapped[int] = mapped_column(ForeignKey("FILE.id"))
    # id_k8sinstance:  Mapped[int] = mapped_column(ForeignKey("K8SINSTANCE.id"))

    # Relationships
    user:    Mapped["User"]       = relationship(foreign_keys=[user_username])
    # project: Mapped["Project"]    = relationship(back_populates="visualizations", lazy="select")
    file:    Mapped["File"]       = relationship(foreign_keys=[id_file])
    # k8sinstance: Mapped["K8sInstance"] = relationship(foreign_keys=[id_k8sinstance], lazy="select")
