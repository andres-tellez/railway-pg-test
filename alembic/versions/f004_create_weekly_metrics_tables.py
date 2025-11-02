"""create weekly_metrics and weekly_decision_log tables

Revision ID: f004
Revises: f003
Create Date: 2026-01-17 17:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f004"
down_revision: Union[str, None] = "f003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create weekly_metrics and weekly_decision_log tables for adaptive training."""
    # Create weekly_metrics table
    op.create_table(
        "weekly_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("week_num", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        # Core metrics (0-100 scores)
        sa.Column("volume_score", sa.DECIMAL(5, 2)),
        sa.Column("intensity_score", sa.DECIMAL(5, 2)),
        sa.Column("consistency_score", sa.DECIMAL(5, 2)),
        # Pace analysis (seconds)
        sa.Column("pace_deviation", sa.DECIMAL(6, 2)),
        sa.Column("avg_actual_pace", sa.DECIMAL(6, 2)),
        sa.Column("avg_planned_pace", sa.DECIMAL(6, 2)),
        # Recovery indicators
        sa.Column("consecutive_missed_days", sa.Integer(), default=0),
        # Training load
        sa.Column("current_week_load", sa.DECIMAL(8, 2)),
        sa.Column("previous_week_load", sa.DECIMAL(8, 2)),
        sa.Column("load_delta_pct", sa.DECIMAL(6, 2)),
        # Dynamic thresholds
        sa.Column("pace_threshold", sa.DECIMAL(6, 2)),
        sa.Column("hr_threshold", sa.DECIMAL(6, 2)),
        # Composite score
        sa.Column("match_score", sa.DECIMAL(4, 2)),
        # Context (future enhancement)
        sa.Column("context_score", postgresql.JSONB(astext_type=sa.Text())),
        # Metadata
        sa.Column("phase", sa.String(20)),
        sa.Column("weeks_remaining", sa.Integer()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP,
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("plan_id", "week_num", name="uq_plan_week"),
    )

    # Create index on plan_id for faster lookups
    op.create_index(
        "idx_weekly_metrics_plan_id",
        "weekly_metrics",
        ["plan_id"],
    )

    # Create index on week_start_date for trend analysis
    op.create_index(
        "idx_weekly_metrics_week_start",
        "weekly_metrics",
        ["week_start_date"],
    )

    # Create weekly_decision_log table
    op.create_table(
        "weekly_decision_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("week_num", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        # Decision details
        sa.Column("decision_type", sa.String(50)),  # "fatigue_reduction", etc.
        sa.Column("trigger_reason", sa.Text()),  # Human-readable explanation
        # Metrics used (JSON)
        sa.Column(
            "metrics_json", postgresql.JSONB(astext_type=sa.Text())
        ),  # All 6 metrics + trends
        # Adjustments applied (JSON)
        sa.Column(
            "adjustments_json", postgresql.JSONB(astext_type=sa.Text())
        ),  # Volume, pace, quality changes
        # Composite score
        sa.Column("match_score", sa.DECIMAL(4, 2)),
        # Context
        sa.Column("phase", sa.String(20)),
        sa.Column("weeks_remaining", sa.Integer()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create index on plan_id for faster lookups
    op.create_index(
        "idx_weekly_decision_log_plan_id",
        "weekly_decision_log",
        ["plan_id"],
    )

    # Create index on week_num for trend analysis
    op.create_index(
        "idx_weekly_decision_log_week_num",
        "weekly_decision_log",
        ["plan_id", "week_num"],
    )


def downgrade() -> None:
    """Drop weekly_metrics and weekly_decision_log tables."""
    op.drop_index("idx_weekly_decision_log_week_num", table_name="weekly_decision_log")
    op.drop_index("idx_weekly_decision_log_plan_id", table_name="weekly_decision_log")
    op.drop_table("weekly_decision_log")
    op.drop_index("idx_weekly_metrics_week_start", table_name="weekly_metrics")
    op.drop_index("idx_weekly_metrics_plan_id", table_name="weekly_metrics")
    op.drop_table("weekly_metrics")
