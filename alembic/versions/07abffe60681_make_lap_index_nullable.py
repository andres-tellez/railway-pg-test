"""Make lap_index nullable

Revision ID: 07abffe60681
Revises: 475a80332c46
Create Date: 2025-06-16 18:55:24.799414
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '07abffe60681'
down_revision: Union[str, None] = '475a80332c46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Allow 'lap_index' in 'splits' table to be nullable."""
    op.alter_column(
        'splits',
        'lap_index',
        existing_type=sa.Integer(),
        nullable=True
    )

def downgrade() -> None:
    """Revert 'lap_index' column in 'splits' table to NOT NULL."""
    op.alter_column(
        'splits',
        'lap_index',
        existing_type=sa.Integer(),
        nullable=False
    )
