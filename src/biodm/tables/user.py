from typing import TYPE_CHECKING, List
from uuid import UUID

from sqlalchemy import Column, Uuid, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from biodm.components.table import Base
from .asso import asso_user_group

if TYPE_CHECKING:
    from .group import Group


class User(Base):
    """User table -> Not locally storing passwords."""
    # KC ENDPOINT: /auth/admin/realms/{realm-name}/users/{id}
    # nullable=False is a problem when creating parent entity with just the User.name.
    # id on creation is ensured by read_or_create method from KCService subclasses.
    id: Mapped[str] = mapped_column(nullable=True)
    username = Column(String(50), nullable=False, primary_key=True)
    email = Column(String(100))
    # camecase exception: direct mapping for keycloak fields
    firstName = Column(String(50))
    lastName = Column(String(50))

    groups: Mapped[List["Group"]] = relationship(
        secondary=asso_user_group,
        back_populates="users"
    )
