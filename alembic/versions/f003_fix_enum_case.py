"""fix enum case to uppercase

Revision ID: f003
Revises: f002
Create Date: 2025-10-13

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f003"
down_revision = "f002"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old enum and recreate with uppercase values
    # First, we need to alter the column to not use the enum
    op.execute("ALTER TABLE webhook_events ALTER COLUMN status TYPE VARCHAR(20)")
    
    # Drop the old enum
    op.execute("DROP TYPE webhookeventstatus")
    
    # Create new enum with uppercase values
    op.execute("""
        CREATE TYPE webhookeventstatus AS ENUM (
            'PENDING',
            'PROCESSING', 
            'COMPLETED',
            'FAILED',
            'IGNORED'
        )
    """)
    
    # Update existing data to uppercase (if any exists)
    op.execute("""
        UPDATE webhook_events 
        SET status = UPPER(status)
        WHERE status IN ('pending', 'processing', 'completed', 'failed', 'ignored')
    """)
    
    # Convert column back to enum type
    op.execute("""
        ALTER TABLE webhook_events 
        ALTER COLUMN status TYPE webhookeventstatus 
        USING status::webhookeventstatus
    """)


def downgrade():
    # Revert back to lowercase
    op.execute("ALTER TABLE webhook_events ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("DROP TYPE webhookeventstatus")
    
    op.execute("""
        CREATE TYPE webhookeventstatus AS ENUM (
            'pending',
            'processing',
            'completed', 
            'failed',
            'ignored'
        )
    """)
    
    op.execute("""
        UPDATE webhook_events
        SET status = LOWER(status)
        WHERE status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'IGNORED')
    """)
    
    op.execute("""
        ALTER TABLE webhook_events
        ALTER COLUMN status TYPE webhookeventstatus
        USING status::webhookeventstatus
    """)

