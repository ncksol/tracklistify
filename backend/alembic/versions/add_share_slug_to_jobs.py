"""add share_slug to jobs

Revision ID: f2a3b4c5d6e7
Revises: e1c9f0bf9de7
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1c9f0bf9de7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add share_slug column to jobs table
    op.add_column('jobs', sa.Column('share_slug', sa.String(), nullable=True))
    
    # Create unique index on share_slug
    op.create_index('ix_jobs_share_slug', 'jobs', ['share_slug'], unique=True)


def downgrade() -> None:
    # Drop index and column
    op.drop_index('ix_jobs_share_slug', table_name='jobs')
    op.drop_column('jobs', 'share_slug')
