# src/db/models/user_athletes.py
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
    String,
)
from src.db.db_session import Base


class UserAthlete(Base):
    __tablename__ = "user_athletes"

    id = Column(Integer, primary_key=True)

    # Stores Auth0 sub (e.g., "google-oauth2|123") and references providers table
    user_id = Column(
        String,
        ForeignKey("user_auth_providers.full_provider_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Internal athlete id used by tokens/activities
    athlete_id = Column(Integer, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_athletes_user_id"),
        UniqueConstraint("athlete_id", name="uq_user_athletes_athlete_id"),
    )
