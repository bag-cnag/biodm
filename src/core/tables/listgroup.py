from typing import List, TYPE_CHECKING

from sqlalchemy import Column, Integer
from sqlalchemy.orm import Mapped, relationship

from core.components.table import Base
from .asso import asso_list_group

if TYPE_CHECKING:
    from .group import Group

class ListGroup(Base):
    id = Column(Integer, primary_key=True)

    groups: Mapped[List["Group"]] = relationship(
        secondary=asso_list_group, 
        cascade="all, delete-orphan",
        single_parent=True
    )