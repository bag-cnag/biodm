from uuid import UUID

from sqlalchemy import Column, String, ForeignKey, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from biodm.components import Base
from biodm.utils.utils import utcnow

class K8sInstance(Base):
    """K8Instance table."""
    # id = Column(Uuid, nullable=False, primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    username_user = mapped_column(ForeignKey('USER.username'), nullable=False)
    namespace = Column(String(50))
    manifest = Column(String(50))

    emited_at = Column(TIMESTAMP(timezone=True),
                       default=utcnow,
                       nullable=False)
    expiring_at = Column(TIMESTAMP(timezone=True))
