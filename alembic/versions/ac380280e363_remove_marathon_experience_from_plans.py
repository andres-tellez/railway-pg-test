"""remove_marathon_experience_from_plans

Revision ID: ac380280e363
Revises: 68fb1c68aa1b
Create Date: 2025-10-31 09:32:00.842559

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ac380280e363"
down_revision: Union[str, None] = "68fb1c68aa1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove marathon_experience column from plans table."""
    op.drop_column("plans", "marathon_experience")


def downgrade() -> None:
    """Re-add marathon_experience column to plans table."""
    op.add_column(
        "plans", sa.Column("marathon_experience", sa.String(50), nullable=True)
    )
