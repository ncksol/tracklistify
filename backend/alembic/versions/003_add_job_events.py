"""add job events table

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-02-16 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job_events table
    op.create_table(
        'job_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('phase', sa.String(), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on (job_id, timestamp) for efficient querying
    op.create_index('ix_job_events_job_id_timestamp', 'job_events', ['job_id', 'timestamp'])


def downgrade() -> None:
    # Drop index and table
    op.drop_index('ix_job_events_job_id_timestamp', table_name='job_events')
    op.drop_table('job_events')
