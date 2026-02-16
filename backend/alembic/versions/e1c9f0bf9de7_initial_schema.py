"""initial schema

Revision ID: e1c9f0bf9de7
Revises: 
Create Date: 2026-02-16 11:54:53.571323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e1c9f0bf9de7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('youtube_url', sa.String(), nullable=False),
        sa.Column('video_title', sa.String(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('QUEUED', 'DOWNLOADING', 'SEGMENTING', 'FINGERPRINTING', 'AGGREGATING', 'COMPLETE', 'FAILED', name='jobstatus'), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create tracks table
    op.create_table(
        'tracks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('start_time_ms', sa.Integer(), nullable=False),
        sa.Column('end_time_ms', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('artist', sa.String(), nullable=True),
        sa.Column('album', sa.String(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('is_transition', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_manual_edit', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unidentified_segments table
    op.create_table(
        'unidentified_segments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_time_ms', sa.Integer(), nullable=False),
        sa.Column('end_time_ms', sa.Integer(), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop tables in reverse order to respect foreign key constraints
    op.drop_table('unidentified_segments')
    op.drop_table('tracks')
    op.drop_table('jobs')
