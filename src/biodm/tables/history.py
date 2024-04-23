from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Column, String, Integer, ForeignKey, TIMESTAMP, text
from sqlalchemy.orm import Mapped, relationship

from biodm.components import Base

if TYPE_CHECKING:
    from .user import User


class History(Base):
    timestamp = Column(TIMESTAMP(timezone=True), server_default=text('now()'), 
                       nullable=False, primary_key=True)
    username_user = Column(ForeignKey('USER.username'), primary_key=True)

    content = Column(String(100), nullable=False)
    endpoint = Column(String(20), nullable=False)
    method = Column(String(20), nullable=False)
