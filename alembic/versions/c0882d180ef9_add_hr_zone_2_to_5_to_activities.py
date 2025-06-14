"""add hr_zone_2_to_5 to activities

Revision ID: c0882d180ef9
Revises: 74a21806400c
Create Date: 2025-06-14 12:40:49.255960

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0882d180ef9'
down_revision: Union[str, None] = '74a21806400c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('activities', sa.Column('hr_zone_2', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('hr_zone_3', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('hr_zone_4', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('hr_zone_5', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('activities', 'hr_zone_5')
    op.drop_column('activities', 'hr_zone_4')
    op.drop_column('activities', 'hr_zone_3')
    op.drop_column('activities', 'hr_zone_2')
    # ### end Alembic commands ###
