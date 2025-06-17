"""Change split column to Integer

Revision ID: 9c644d51853a
Revises: 475a80332c46
Create Date: 2025-06-16 XX:XX:XX.XXX
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c644d51853a'
down_revision = '475a80332c46'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing split column (if Boolean) and re-add as Integer
    with op.batch_alter_table('splits') as batch_op:
        batch_op.drop_column('split')
        batch_op.add_column(sa.Column('split', sa.Integer(), nullable=True))


def downgrade():
    # Revert to Boolean type if downgrading
    with op.batch_alter_table('splits') as batch_op:
        batch_op.drop_column('split')
        batch_op.add_column(sa.Column('split', sa.Boolean(), nullable=True))
