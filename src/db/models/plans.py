# src/db/models/plans.py

from sqlalchemy import (
    JSON,
    Column,
    Integer,
    String,
    Date,
    Text,
    TIMESTAMP,
    ForeignKey,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.db_session import Base
from src.db.models.user_profile import SqliteArray  # SQLite-compatible array type

# *** Important: import PlanWorkout here so class is known before mapping
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.user_identity import UserIdentity


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_name = Column(String(255), nullable=False)
    race_date = Column(Date, nullable=True)
    race_distance = Column(String(32), nullable=True)
    race_name = Column(String(255), nullable=True)
    race_location = Column(String(255), nullable=True)
    race_metadata = Column(
        JSON,
        nullable=True,
        comment="Race metadata (terrain, elevation, course type, etc.)",
    )
    primary_goal = Column(String(50), nullable=True)
    target_time = Column(String(20), nullable=True)
    training_days = Column(SqliteArray(), nullable=True)  # SQLite-compatible array
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="false")

    context_snapshot = Column(
        JSON,
        nullable=True,
        comment="Optional reasoning snapshot from plan generation (validation spine, decision_trace, metadata).",
    )

    created_by = Column(String(32), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    workouts = relationship(
        "PlanWorkout", back_populates="plan", cascade="all, delete-orphan"
    )
    user = relationship("UserIdentity", back_populates="plans")
