from typing import Optional, List, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased, attribute_keyed_dict
from sqlalchemy.types import Uuid
from typing import Dict

from biodm.components import Base
from .asso import asso_user_group


if TYPE_CHECKING:
    from .user import User


class Group(Base):
    """Group table."""
    # GroupAlias = aliased("Group")
    # nullable=False is a problem when creating parent entity with just the User.username.
    # id on creation is ensured by read_or_create method from KCService subclasses.
    id: Mapped[UUID] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    # test
    n_members: Mapped[int] = mapped_column(nullable=True)
    name_parent: Mapped[Optional[str]] = mapped_column(String, ForeignKey("GROUP.name"), nullable=True)

    # relationships
    users: Mapped[List["User"]] = relationship(
        secondary=asso_user_group,
        back_populates="groups",
        # init=False,
    )


    # children: Mapped[Dict[str, "Group"]] = relationship(
    #     cascade="all, delete-orphan",
    #     back_populates="parent",
    #     collection_class=attribute_keyed_dict("name"),
    # )

    # parent: Mapped[Optional["Group"]] = relationship(
    #     back_populates="children", remote_side=name
    # )

    children: Mapped[List["Group"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="parent",
    )
    parent: Mapped[Optional["Group"]] = relationship(
        back_populates="children", remote_side=[name],
    )
    # projects: Mapped[List["Project"]] = relationship(
    #     secondary=asso_project_group, back_populates="groups"
    # )
    # datasets: Mapped[List["Dataset"]] = relationship(back_populates="group")

    def __repr__(self):
        return f"<Group(name={self.name}, parent={str(self.parent)})>"
