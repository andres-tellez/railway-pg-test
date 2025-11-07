"""change user_id to string

Revision ID: dbb359f494c5
Revises: 8d0c1460527f
Create Date: 2025-09-10 18:36:55.979032

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dbb359f494c5"
down_revision: str = "8d0c1460527f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert user_identity.user_id to String
    op.alter_column(
        "user_identity",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(),
        type_=sa.String(),
        postgresql_using="user_id::text",
    )

    # Convert user_athletes.user_id to String
    op.alter_column(
        "user_athletes",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(),
        type_=sa.String(),
        postgresql_using="user_id::text",
    )

    # Convert user_profile.user_id to String
    op.alter_column(
        "user_profile",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(),
        type_=sa.String(),
        postgresql_using="user_id::text",
    )


def downgrade() -> None:
    # Revert user_identity.user_id back to UUID
    op.alter_column(
        "user_identity",
        "user_id",
        existing_type=sa.String(),
        type_=sa.dialects.postgresql.UUID(),
        postgresql_using="user_id::uuid",
    )

    # Revert user_athletes.user_id back to UUID
    op.alter_column(
        "user_athletes",
        "user_id",
        existing_type=sa.String(),
        type_=sa.dialects.postgresql.UUID(),
        postgresql_using="user_id::uuid",
    )

    # Revert user_profile.user_id back to UUID
    op.alter_column(
        "user_profile",
        "user_id",
        existing_type=sa.String(),
        type_=sa.dialects.postgresql.UUID(),
        postgresql_using="user_id::uuid",
    )
