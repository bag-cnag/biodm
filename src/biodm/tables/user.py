from typing import TYPE_CHECKING, List

from sqlalchemy import Column, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from biodm import config
from biodm.components.table import Base
from .asso import asso_user_group

if TYPE_CHECKING:
    from .group import Group


class User(Base):
    """User table -> Not locally storing passwords."""
    # KC ENDPOINT: /auth/admin/realms/{realm-name}/users/{id}
    id: Mapped[str] = mapped_column(nullable=not (config.KC_HOST and config.KC_REALM))
    username = Column(String(50), nullable=False, primary_key=True)
    email = Column(String(100))
    # camecase exception: direct mapping for keycloak fields
    firstName = Column(String(50))
    lastName = Column(String(50))

    groups: Mapped[List["Group"]] = relationship(
        secondary=asso_user_group,
        back_populates="users",
        lazy="joined"
    )
