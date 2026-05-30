# src/db/models/plan_workouts.py

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from src.db.db_session import Base
from sqlalchemy.dialects import postgresql
from src.db.models.user_profile import SqliteJSONB  # For SQLite compatibility


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
    # New structured fields
    target_zone = sa.Column(sa.String, nullable=True)
    target_hr = sa.Column(sa.String, nullable=True)
    focus = sa.Column(sa.String, nullable=True)
    segments = sa.Column(
        SqliteJSONB(), nullable=True, comment="Spec-compliant segments JSON"
    )

    # ✅ New metadata fields (all nullable for backward compatibility)
    run_type_key = sa.Column(
        sa.Text,
        nullable=True,
        comment="Taxonomy key: easy|tempo|threshold|long_run|intervals|hills|race",
    )
    phase = sa.Column(
        sa.Text, nullable=True, comment="Training phase: Base|Build|Peak|Taper"
    )
    pace_ranges = sa.Column(
        SqliteJSONB(),
        nullable=True,
        comment="Pace ranges: {z2:[sec,sec], z3:[...], z4:[...], m:[...]}",
    )
    allow_quality = sa.Column(
        sa.Boolean, nullable=True, comment="Whether quality elements allowed"
    )
    cues = sa.Column(
        sa.Text, nullable=True, comment="Athlete-facing workout cues/guidance"
    )
    quality_insert = sa.Column(
        SqliteJSONB(),
        nullable=True,
        comment="Quality insert metadata: {type: 'marathon_finish'|'strides', miles: ...}",
    )

    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("plan_id", "date", name="uq_plan_date"),
        sa.CheckConstraint(
            "run_type_key IN ('easy','tempo','threshold','long_run','intervals','hills','race')",
            name="chk_run_type_key",
        ),
        sa.Index("idx_plan_workouts_plan_date", "plan_id", "date"),
    )

    plan = relationship("Plan", back_populates="workouts")
