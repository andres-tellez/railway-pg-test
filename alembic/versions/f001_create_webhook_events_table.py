"""create webhook_events table

Revision ID: f001
Revises: 66e2d9242637
Create Date: 2025-10-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f001'
down_revision = '66e2d9242637'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum type for webhook event status
    webhook_status_enum = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed', 'ignored',
        name='webhookeventstatus',
        create_type=True
    )
    webhook_status_enum.create(op.get_bind(), checkfirst=True)

    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('object_type', sa.String(), nullable=False),
        sa.Column('object_id', sa.Integer(), nullable=False),
        sa.Column('aspect_type', sa.String(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=True),
        sa.Column('event_time', sa.Integer(), nullable=True),
        sa.Column('updates', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', webhook_status_enum, nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('received_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on status for faster queries
    op.create_index('ix_webhook_events_status', 'webhook_events', ['status'])

    # Create index on owner_id for faster user lookups
    op.create_index('ix_webhook_events_owner_id', 'webhook_events', ['owner_id'])

    # Create composite index for deduplication checks
    op.create_index(
        'ix_webhook_events_object',
        'webhook_events',
        ['object_type', 'object_id', 'aspect_type'],
    )


def downgrade():
    # Drop indexes
    op.drop_index('ix_webhook_events_object', table_name='webhook_events')
    op.drop_index('ix_webhook_events_owner_id', table_name='webhook_events')
    op.drop_index('ix_webhook_events_status', table_name='webhook_events')

    # Drop table
    op.drop_table('webhook_events')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS webhookeventstatus')
