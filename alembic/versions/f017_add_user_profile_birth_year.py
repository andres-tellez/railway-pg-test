"""Add birth_year to user_profile

Revision ID: f017
Revises: f016
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f017"
down_revision: Union[str, None] = "f016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("birth_year", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profile", "birth_year")
