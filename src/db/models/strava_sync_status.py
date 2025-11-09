from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    ForeignKey,
    func,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import Base


class StravaSyncStatus(Base):
    __tablename__ = "strava_sync_status"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        String,
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_id = Column(Integer, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending")
    progress = Column(Float, nullable=False, default=0.0)
    step = Column(String(255), nullable=True)
    detail = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
