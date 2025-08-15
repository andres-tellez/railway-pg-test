"""create user_identity table

Revision ID: 5b78f775382c
Revises: 95b85d34696c
Create Date: 2025-08-07 19:29:40.599271
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5b78f775382c"
down_revision: Union[str, None] = "95b85d34696c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # 4️⃣ Create user_identity table
    op.create_table(
        "user_identity",
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("picture", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    # Drop user_identity table
    op.drop_table("user_identity")
