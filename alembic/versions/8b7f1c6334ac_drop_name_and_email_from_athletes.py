"""drop name and email from athletes

Revision ID: 8b7f1c6334ac
Revises: eae080f38d44
Create Date: 2025-08-10 14:56:34.091408
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8b7f1c6334ac"
down_revision = "eae080f38d44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode for widest compatibility
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.drop_column("name")
        batch_op.drop_column("email")


def downgrade() -> None:
    # Restore columns as nullable to avoid breaking historical rows
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
