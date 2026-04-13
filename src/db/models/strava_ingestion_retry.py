"""Persisted Strava ingestion retries (survives process restarts)."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from src.db.db_session import Base


class StravaIngestionRetry(Base):
    """
    One row per (user_id, athlete_id): deferred ingestion (e.g. headroom) will run
    after run_at. claimed_at prevents double pickup across workers.
    """

    __tablename__ = "strava_ingestion_retry"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "athlete_id",
            name="uq_strava_ingestion_retry_user_athlete",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String,
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_id = Column(Integer, nullable=False, index=True)
    run_after = Column(DateTime(timezone=True), nullable=False, index=True)
    attempt = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    claimed_at = Column(DateTime(timezone=True), nullable=True)
