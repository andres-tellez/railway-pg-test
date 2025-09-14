"""drop created_by from plans

Revision ID: 6d996face68b
Revises: 93fd4036c12d
Create Date: 2025-09-13 13:06:21.152392
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6d996face68b"
down_revision: Union[str, None] = "93fd4036c12d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: drop created_by column from plans."""
    op.drop_column("plans", "created_by")


def downgrade() -> None:
    """Downgrade schema: re-add created_by column to plans."""
    op.add_column(
        "plans",
        sa.Column("created_by", sa.String(), nullable=True),
    )
