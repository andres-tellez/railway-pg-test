"""Fix split column back to INTEGER"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'f23968f5fa38'
down_revision: Union[str, None] = '07abffe60681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        ALTER TABLE splits 
        ALTER COLUMN split TYPE INTEGER 
        USING split::INTEGER
    """)

def downgrade() -> None:
    op.execute("""
        ALTER TABLE splits 
        ALTER COLUMN split TYPE INTEGER 
        USING CASE
            WHEN split = TRUE THEN 1
            WHEN split = FALSE THEN 0
            ELSE NULL
        END
    """)
