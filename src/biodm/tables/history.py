from sqlalchemy import Column, String, ForeignKey, TIMESTAMP, Text
from sqlalchemy.orm import mapped_column, Mapped

from biodm.components import Base
from biodm.utils.utils import utcnow

class History(Base):
    """History table."""
    timestamp = Column(TIMESTAMP(timezone=True), default=utcnow,
                       nullable=False, primary_key=True)
    user_username: Mapped[str] = mapped_column(String(100), primary_key=True)

    content = Column(Text, nullable=False)
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
