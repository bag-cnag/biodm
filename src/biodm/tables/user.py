from typing import TYPE_CHECKING, List

from sqlalchemy import Column, Uuid, String
from sqlalchemy.orm import Mapped, relationship

from biodm.components.table import Base
from .asso import asso_user_group

if TYPE_CHECKING:
    from .group import Group


class User(Base):
    """User table -> Not locally storing passwords."""
    # KC ENDPOINT: /auth/admin/realms/{realm-name}/users/{id}
    id = Column(Uuid, unique=True)
    username = Column(String(50), nullable=False, primary_key=True)
    email = Column(String(100))
    first_name = Column(String(50))
    last_name = Column(String(50))

    groups: Mapped[List["Group"]] = relationship(
        secondary=asso_user_group,
        back_populates="users"
    )
