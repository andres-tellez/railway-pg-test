"""add tokens table

Revision ID: 30b4094623ae
Revises: c0882d180ef9
Create Date: 2025-06-14 16:29:28.137300

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30b4094623ae'
down_revision: Union[str, None] = 'c0882d180ef9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('tokens',
        sa.Column('athlete_id', sa.BigInteger(), primary_key=True),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('refresh_token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False)
    )



def downgrade() -> None:
    """Downgrade schema."""
    pass
