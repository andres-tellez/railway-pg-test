from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from src.db.db_session import Base


class UserCoachPreferences(Base):
    __tablename__ = "user_coach_preferences"

    user_id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    coaching_level = Column(String, nullable=False, server_default="beginner")
    run_summary_priority = Column(JSONB)
    training_summary_priority = Column(JSONB)
    verbosity = Column(String, nullable=False, server_default="normal")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
