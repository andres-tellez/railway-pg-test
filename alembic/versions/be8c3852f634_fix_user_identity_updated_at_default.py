"""fix user_identity.updated_at default

Revision ID: be8c3852f634
Revises: 6668668c263f
Create Date: 2025-09-13 22:17:14.460760
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "be8c3852f634"
down_revision: Union[str, None] = "6668668c263f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: ensure updated_at has default NOW()."""
    op.alter_column(
        "user_identity",
        "updated_at",
        server_default=sa.func.now(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema: remove default on updated_at."""
    op.alter_column(
        "user_identity",
        "updated_at",
        server_default=None,
        existing_nullable=False,
    )
