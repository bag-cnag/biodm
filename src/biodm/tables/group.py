from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Column, String, Integer, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, relationship

from biodm.components import Base
from .asso import asso_user_group

if TYPE_CHECKING:
    from .user import User


class Group(Base):
    """Group table."""
    id = Column(Uuid, unique=True)
    name: Mapped[str] = Column(String(100), primary_key=True)
    # test
    n_members: Mapped[int] = Column(Integer, nullable=True)
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
    # datasets: Mapped[List["Dataset"]] = relationship(back_populates="group")

    def __repr__(self):
        return f"<Group(name={self.name}, parent={str(self.parent)})>"


