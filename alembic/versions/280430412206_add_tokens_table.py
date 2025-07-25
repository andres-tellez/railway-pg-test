"""Add tokens table

Revision ID: 280430412206
Revises: a01b22564ade
Create Date: 2025-06-14 23:41:27.438877
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '280430412206'
down_revision: Union[str, None] = 'a01b22564ade'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tokens',
        sa.Column('athlete_id', sa.BigInteger(), nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('refresh_token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('athlete_id')
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('tokens')
