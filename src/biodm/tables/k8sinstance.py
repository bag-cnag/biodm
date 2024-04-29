from sqlalchemy import Column, String, ForeignKey, TIMESTAMP, text, UUID

from biodm.components import Base


class K8sInstance(Base):
    """K8Instance table."""
    id = Column(UUID, nullable=False, primary_key=True)
    username_user = Column(ForeignKey('USER.username'), nullable=False)
    namespace = Column(String(50))
    manifest = Column(String(50))


    emited_at = Column(TIMESTAMP(timezone=True), 
                       server_default=text('now()'), 
                       nullable=False)
    expiring_at = Column(TIMESTAMP(timezone=True))
