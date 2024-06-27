from sqlalchemy import Column, String, ForeignKey, TIMESTAMP
from sqlalchemy.orm import mapped_column

from biodm.components import Base
from biodm.utils.utils import utcnow

class History(Base):
    """History table."""
    timestamp = Column(TIMESTAMP(timezone=True), default=utcnow,
                       nullable=False, primary_key=True)
    username_user = mapped_column(ForeignKey('USER.username'), primary_key=True)

    content = Column(String(2000), nullable=False)
    endpoint = Column(String(20), nullable=False)
    method = Column(String(20), nullable=False)
