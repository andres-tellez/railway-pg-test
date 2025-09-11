"""Fix FK: user_athletes.user_id → user_identity

Revision ID: 8d0c1460527f
Revises: e55a924cbe7e
Create Date: 2025-09-10 09:18:54.121184

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision = "8d0c1460527f"
down_revision = "e55a924cbe7e"
branch_labels = None
depends_on = None


def upgrade():
    # 🔁 Drop the old foreign key from user_auth_providers
    # This is already done manually, so skip it now
    # op.drop_constraint(
    #     "fk_user_athletes_user_id",
    #     "user_athletes",
    #     type_="foreignkey",
    # )

    # ✅ Add new FK to user_identity
    op.create_foreign_key(
        "fk_user_athletes_user_identity",
        "user_athletes",
        "user_identity",
        ["user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )


def downgrade():
    # ⬅️ Revert to previous FK if needed
    op.drop_constraint(
        "fk_user_athletes_user_identity", "user_athletes", type_="foreignkey"
    )

    op.create_foreign_key(
        "fk_user_athletes_user_id",  # ← recreate the original
        "user_athletes",
        "user_auth_providers",
        ["user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
