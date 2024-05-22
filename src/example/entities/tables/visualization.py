from typing import TYPE_CHECKING, List

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, relationship

from biodm.components.table import Base
from .asso import asso_dataset_tag

if TYPE_CHECKING:
    from .project import Project
    from biodm.tables import K8sinstance


class Visualization(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String)

    id_project:      Mapped[int] = Column(ForeignKey("PROJECT.id"))
    id_k8sinstance:  Mapped[int] = Column(ForeignKey("K8SINSTANCE.id"))

    # k8sinstance: Mapped["K8sinstance"] = relationship(foreign_keys=[id_k8sinstance], lazy="select")
    project: Mapped["Project"]    = relationship(back_populates="visualizations", lazy="select")
