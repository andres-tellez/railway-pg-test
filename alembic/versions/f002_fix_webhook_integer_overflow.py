"""fix webhook integer overflow

Revision ID: f002
Revises: f001
Create Date: 2025-10-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f002'
down_revision = 'f001'
branch_labels = None
depends_on = None


def upgrade():
    # Change object_id from INTEGER to BIGINT
    op.alter_column('webhook_events', 'object_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)
    
    # Change owner_id from INTEGER to BIGINT  
    op.alter_column('webhook_events', 'owner_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)
    
    # Change subscription_id from INTEGER to BIGINT
    op.alter_column('webhook_events', 'subscription_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)
    
    # Change event_time from INTEGER to BIGINT
    op.alter_column('webhook_events', 'event_time',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)


def downgrade():
    # Revert back to INTEGER (may cause data loss for large values)
    op.alter_column('webhook_events', 'event_time',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)
    
    op.alter_column('webhook_events', 'subscription_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)
    
    op.alter_column('webhook_events', 'owner_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False)
    
    op.alter_column('webhook_events', 'object_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False)
