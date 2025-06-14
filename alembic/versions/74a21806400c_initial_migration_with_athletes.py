"""initial migration with athletes

Revision ID: 74a21806400c
Revises: 
Create Date: 2025-06-14 12:14:53.762025
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '74a21806400c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('activities',
        sa.Column('activity_id', sa.BigInteger(), nullable=False),
        sa.Column('athlete_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('distance', sa.Float(), nullable=True),
        sa.Column('elapsed_time', sa.Integer(), nullable=True),
        sa.Column('moving_time', sa.Integer(), nullable=True),
        sa.Column('total_elevation_gain', sa.Float(), nullable=True),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('timezone', sa.String(), nullable=True),
        sa.Column('average_speed', sa.Float(), nullable=True),
        sa.Column('max_speed', sa.Float(), nullable=True),
        sa.Column('suffer_score', sa.Float(), nullable=True),
        sa.Column('average_heartrate', sa.Float(), nullable=True),
        sa.Column('max_heartrate', sa.Float(), nullable=True),
        sa.Column('calories', sa.Float(), nullable=True),
        sa.Column('conv_distance', sa.Float(), nullable=True),
        sa.Column('conv_elevation_feet', sa.Float(), nullable=True),
        sa.Column('conv_avg_speed', sa.Float(), nullable=True),
        sa.Column('conv_max_speed', sa.Float(), nullable=True),
        sa.Column('conv_moving_time', sa.String(), nullable=True),
        sa.Column('conv_elapsed_time', sa.String(), nullable=True),
        sa.Column('hr_zone_1', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('activity_id')
    )
    op.create_index(op.f('ix_activities_activity_id'), 'activities', ['activity_id'], unique=False)
    op.create_index(op.f('ix_activities_athlete_id'), 'activities', ['athlete_id'], unique=False)

    op.create_table('athletes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strava_athlete_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strava_athlete_id')
    )

    op.create_table('splits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.BigInteger(), nullable=False),
        sa.Column('lap_index', sa.Integer(), nullable=False),
        sa.Column('distance', sa.Float(), nullable=True),
        sa.Column('elapsed_time', sa.Integer(), nullable=True),
        sa.Column('moving_time', sa.Integer(), nullable=True),
        sa.Column('average_speed', sa.Float(), nullable=True),
        sa.Column('max_speed', sa.Float(), nullable=True),
        sa.Column('start_index', sa.Integer(), nullable=True),
        sa.Column('end_index', sa.Integer(), nullable=True),
        sa.Column('split', sa.Boolean(), nullable=True),
        sa.Column('average_heartrate', sa.Float(), nullable=True),
        sa.Column('pace_zone', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('conv_distance', sa.Float(), nullable=True),
        sa.Column('conv_avg_speed', sa.Float(), nullable=True),
        sa.Column('conv_moving_time', sa.String(), nullable=True),
        sa.Column('conv_elapsed_time', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.activity_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activity_id', 'lap_index', name='uq_activity_lap')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('splits')
    op.drop_table('athletes')
    op.drop_index(op.f('ix_activities_athlete_id'), table_name='activities')
    op.drop_index(op.f('ix_activities_activity_id'), table_name='activities')
    op.drop_table('activities')
