from typing import List, TYPE_CHECKING

from sqlalchemy import Column, Integer
from sqlalchemy.orm import Mapped, relationship

from biodm.components import Base
from .asso import asso_list_group

if TYPE_CHECKING:
    from .group import Group


class ListGroup(Base):
    """ListGroup table."""
    id = Column(Integer, primary_key=True)

    groups: Mapped[List["Group"]] = relationship(
        secondary=asso_list_group,
    )
