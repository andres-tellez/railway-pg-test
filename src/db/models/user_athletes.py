# src/db/models/user_athletes.py
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
    String,
    Boolean,
)
from src.db.db_session import Base


class UserAthleteLink(Base):
    __tablename__ = "user_athletes"

    id = Column(Integer, primary_key=True)

    # Stores internal UUID (user_id) referencing user_identity.user_id
    user_id = Column(
        String,
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Internal athlete id used by tokens/activities
    athlete_id = Column(Integer, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Strava Premium/Summit subscription status
    # Extracted from OAuth response athlete.summit field
    has_strava_premium = Column(
        Boolean, nullable=True
    )  # True if Summit/paid, False if free, None if unknown
    strava_premium_checked_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When we last checked/updated premium status

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_athletes_user_id"),
        UniqueConstraint("athlete_id", name="uq_user_athletes_athlete_id"),
    )
