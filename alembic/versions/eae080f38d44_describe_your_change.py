"""No schema changes in this revision.

Revision ID: eae080f38d44
Revises: f8658ef62c5f
Create Date: 2025-08-07 19:58:05.607531
"""

from typing import Sequence, Union

# Revision identifiers, used by Alembic.
revision: str = "eae080f38d44"
down_revision: Union[str, None] = "f8658ef62c5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - no changes."""


def downgrade() -> None:
    """Downgrade schema - no changes."""
