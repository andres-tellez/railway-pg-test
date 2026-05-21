"""Add Memory v2 foundational tables (state, threads, interactions).

Revision ID: f016
Revises: f015
Create Date: 2026-05-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f016"
down_revision: Union[str, None] = "f015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_state_observations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_identity.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column("body_area", sa.String(length=64), nullable=True),
        sa.Column("intensity", sa.SmallInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "captured_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_until", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_user_state_observations_user_valid_until",
        "user_state_observations",
        ["user_id", "valid_until"],
    )

    op.create_table(
        "user_open_threads",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_identity.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("due_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="open"
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_user_open_threads_user_status_due_at",
        "user_open_threads",
        ["user_id", "status", "due_at"],
    )

    op.create_table(
        "coach_interactions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_identity.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("flag", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column(
            "captured_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "conversation_id",
            "flag",
            "key",
            name="uq_coach_interactions_scope",
        ),
    )
    op.create_index(
        "ix_coach_interactions_user_conversation_captured_at",
        "coach_interactions",
        ["user_id", "conversation_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coach_interactions_user_conversation_captured_at",
        table_name="coach_interactions",
    )
    op.drop_table("coach_interactions")

    op.drop_index(
        "ix_user_open_threads_user_status_due_at",
        table_name="user_open_threads",
    )
    op.drop_table("user_open_threads")

    op.drop_index(
        "ix_user_state_observations_user_valid_until",
        table_name="user_state_observations",
    )
    op.drop_table("user_state_observations")
