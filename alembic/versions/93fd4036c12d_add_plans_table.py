"""add plans table

Revision ID: 93fd4036c12d
Revises: 9cba4583175d
Create Date: 2025-09-13 00:15:31.539768

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "93fd4036c12d"
down_revision: Union[str, None] = "9cba4583175d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
