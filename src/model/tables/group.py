from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import Mapped, relationship

from ..table import Base
from .asso import asso_user_group
if TYPE_CHECKING:
    from .user import User
    from .dataset import Dataset


class Group(Base):
    name: Mapped[str] = Column(String(100), primary_key=True)
    name_parent: Mapped[Optional[int]] = Column(ForeignKey("GROUP.name"), nullable=True)

    # relationships
    users: Mapped[List["User"]] = relationship(
        secondary=asso_user_group, 
        back_populates="groups",
        # init=False,
    )

    children: Mapped[List["Group"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="parent",
        # init=False,
        # repr=False,
    )
    parent: Mapped[Optional["Group"]] = relationship(
        back_populates="children", remote_side=name, #, default=None
        # init=False,
    )
    # projects: Mapped[List["Project"]] = relationship(
    #     secondary=asso_project_group, back_populates="groups"
    # )
    datasets: Mapped[List["Dataset"]] = relationship(back_populates="group")

    def __repr__(self):
        return f"<Group(name={self.name}, parent={str(self.parent)})>"
