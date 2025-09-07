"""create user_athletes link table

Revision ID: a1b2c3d4e5f6
Revises: 8b7f1c6334ac
Create Date: 2025-08-10 15:05:00
"""

from alembic import op
import sqlalchemy as sa

# Set these to match your actual file/revision ids
revision = "a1b2c3d4e5f6"
down_revision = "8b7f1c6334ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_athletes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("athlete_id", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # strict 1:1 mappings
        sa.UniqueConstraint("user_id", name="uq_user_athletes_user_id"),
        sa.UniqueConstraint("athlete_id", name="uq_user_athletes_athlete_id"),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name="fk_user_athletes_athlete",
            ondelete="RESTRICT",
        ),
        # Optional: enforce referential integrity to user_identity if user_id is UNIQUE there.
        # sa.ForeignKeyConstraint(["user_id"], ["user_identity.user_id"], name="fk_user_athletes_user", ondelete="CASCADE"),
    )

    # Helpful for lookups even with the UNIQUE above
    op.create_index("ix_user_athletes_user_id", "user_athletes", ["user_id"])
    op.create_index("ix_user_athletes_athlete_id", "user_athletes", ["athlete_id"])


def downgrade() -> None:
    op.drop_index("ix_user_athletes_athlete_id", table_name="user_athletes")
    op.drop_index("ix_user_athletes_user_id", table_name="user_athletes")
    op.drop_table("user_athletes")
