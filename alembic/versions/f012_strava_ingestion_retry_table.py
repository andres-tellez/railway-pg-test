"""Durable Strava ingestion retry queue (survives process restarts).

Revision ID: f012
Revises: f011
Create Date: 2026-04-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f012"
down_revision: Union[str, None] = "f011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strava_ingestion_retry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("athlete_id", sa.Integer(), nullable=False),
        sa.Column(
            "run_after",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_identity.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "athlete_id",
            name="uq_strava_ingestion_retry_user_athlete",
        ),
    )
    op.create_index(
        "ix_strava_ingestion_retry_user_id",
        "strava_ingestion_retry",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_strava_ingestion_retry_athlete_id",
        "strava_ingestion_retry",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        "ix_strava_ingestion_retry_run_after",
        "strava_ingestion_retry",
        ["run_after"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strava_ingestion_retry_run_after", table_name="strava_ingestion_retry"
    )
    op.drop_index(
        "ix_strava_ingestion_retry_athlete_id", table_name="strava_ingestion_retry"
    )
    op.drop_index(
        "ix_strava_ingestion_retry_user_id", table_name="strava_ingestion_retry"
    )
    op.drop_table("strava_ingestion_retry")
