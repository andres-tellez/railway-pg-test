"""Add enrichment columns

Revision ID: 7f825e52db54
Revises: 0d9cacbda2b0
Create Date: 2025-06-12 02:55:39.116629

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7f825e52db54'
down_revision: Union[str, None] = '0d9cacbda2b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('activities', sa.Column('hr_zone_1_pct', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('hr_zone_2_pct', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('hr_zone_3_pct', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('hr_zone_4_pct', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('hr_zone_5_pct', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('enriched', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('activities', 'enriched')
    op.drop_column('activities', 'hr_zone_5_pct')
    op.drop_column('activities', 'hr_zone_4_pct')
    op.drop_column('activities', 'hr_zone_3_pct')
    op.drop_column('activities', 'hr_zone_2_pct')
    op.drop_column('activities', 'hr_zone_1_pct')
