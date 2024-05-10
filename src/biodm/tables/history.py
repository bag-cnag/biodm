import datetime

from sqlalchemy import Column, String, ForeignKey, TIMESTAMP, text

from biodm.components import Base


class History(Base):
    """History table."""
    timestamp = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow, 
                       nullable=False, primary_key=True)
    username_user = Column(ForeignKey('USER.username'), primary_key=True)

    content = Column(String(100), nullable=False)
    endpoint = Column(String(20), nullable=False)
    method = Column(String(20), nullable=False)
