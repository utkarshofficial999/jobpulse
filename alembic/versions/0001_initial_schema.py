"""initial milestone 1 schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-16 11:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Attempt to enable pgvector extension if running on postgres
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. Sources table
    op.create_table(
        'sources',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('connector_type', sa.String(length=64), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('poll_interval_seconds', sa.Integer(), nullable=False, server_default=sa.text('3600')),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sources_next_run_at', 'sources', ['next_run_at'], unique=False)

    # 2. Raw Jobs table
    op.create_table(
        'raw_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_raw_jobs_source_ext', 'raw_jobs', ['source_id', 'external_id'], unique=False)
    op.create_index('idx_raw_jobs_fetched_at', 'raw_jobs', ['fetched_at'], unique=False)

    # 3. Canonical Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=False),
        sa.Column('locations', sa.JSON(), nullable=False),
        sa.Column('remote_type', sa.String(length=32), nullable=False, server_default='unknown'),
        sa.Column('seniority', sa.String(length=32), nullable=False, server_default='unspecified'),
        sa.Column('employment_type', sa.String(length=32), nullable=False, server_default='unknown'),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('apply_url', sa.Text(), nullable=False),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_jobs_source_external')
    )
    op.create_index('idx_jobs_source_status', 'jobs', ['source_id', 'status'], unique=False)
    op.create_index('idx_jobs_content_hash', 'jobs', ['content_hash'], unique=False)
    op.create_index('idx_jobs_last_seen', 'jobs', ['source_id', 'last_seen_at'], unique=False)


def downgrade() -> None:
    op.drop_table('jobs')
    op.drop_table('raw_jobs')
    op.drop_table('sources')
