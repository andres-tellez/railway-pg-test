# src/db/models/plan_workouts.py

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from src.db.db_session import Base


class PlanWorkout(Base):
    __tablename__ = "plan_workouts"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    plan_id = sa.Column(
        sa.Integer, sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    date = sa.Column(sa.Date, nullable=False)
    workout_type = sa.Column(sa.String, nullable=False)
    description = sa.Column(sa.Text, nullable=False)
    miles = sa.Column(sa.Float, nullable=False)
    intensity = sa.Column(sa.String, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (sa.UniqueConstraint("plan_id", "date", name="uq_plan_date"),)

    plan = relationship("Plan", back_populates="workouts")
