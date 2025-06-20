"""Fix split column type to Boolean

Revision ID: 475a80332c46
Revises: 280430412206
Create Date: 2025-06-16 15:05:23.135910
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '475a80332c46'
down_revision: Union[str, None] = '280430412206'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Convert 'split' column in 'splits' table from INTEGER to BOOLEAN."""
    op.execute("""
        ALTER TABLE splits 
        ALTER COLUMN split TYPE BOOLEAN 
        USING CASE
            WHEN split::INTEGER = 1 THEN TRUE
            WHEN split::INTEGER = 0 THEN FALSE
            ELSE NULL
        END
    """)

def downgrade() -> None:
    """Downgrade not implemented due to potential data loss converting from BOOLEAN back to INTEGER."""
    pass
