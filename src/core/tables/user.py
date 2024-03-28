from typing import TYPE_CHECKING, List

from sqlalchemy import Column, Uuid, String
from sqlalchemy.orm import Mapped, relationship

from core.components.table import Base
from .asso import asso_user_group
if TYPE_CHECKING:
    from .group import Group


class User(Base):
    # KC ENDPOINT: /auth/admin/realms/{realm-name}/users/{id}
    id = Column(Uuid, primary_key=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100))
    first_name = Column(String(50))
    last_name = Column(String(50))

    groups: Mapped[List["Group"]] = relationship(
        secondary=asso_user_group, 
        back_populates="users"
    )
