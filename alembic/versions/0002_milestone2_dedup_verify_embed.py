"""milestone 2 dedup, verify, embed schema

Revision ID: 0002_milestone2
Revises: 0001_initial_schema
Create Date: 2026-10-16 12:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = '0002_milestone2'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = (conn.dialect.name == "postgresql")

    # 1. Create job_clusters table
    op.create_table(
        'job_clusters',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_normalized', sa.String(length=255), nullable=False),
        sa.Column('title_normalized', sa.String(length=512), nullable=False),
        sa.Column('dedup_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('primary_job_id', sa.String(length=36), nullable=True),
        sa.Column('job_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedup_fingerprint', name='uq_job_clusters_fingerprint')
    )
    op.create_index('idx_job_clusters_fingerprint', 'job_clusters', ['dedup_fingerprint'], unique=False)

    # 2. Add columns to jobs table
    op.add_column('jobs', sa.Column('cluster_id', sa.String(length=36), nullable=True))
    op.add_column('jobs', sa.Column('is_primary_in_cluster', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('jobs', sa.Column('verification_status', sa.String(length=32), nullable=False, server_default='unverified'))
    op.add_column('jobs', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('verification_error', sa.Text(), nullable=True))

    if is_postgres:
        op.add_column('jobs', sa.Column('embedding', Vector(384), nullable=True))
    else:
        op.add_column('jobs', sa.Column('embedding', sa.JSON(), nullable=True))

    op.add_column('jobs', sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True))

    # Add foreign keys
    op.create_foreign_key('fk_jobs_cluster_id', 'jobs', 'job_clusters', ['cluster_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_job_clusters_primary_job', 'job_clusters', 'jobs', ['primary_job_id'], ['id'], ondelete='SET NULL')

    # Add indexes
    op.create_index('idx_jobs_cluster_id', 'jobs', ['cluster_id'], unique=False)
    op.create_index('idx_jobs_verification', 'jobs', ['status', 'verification_status'], unique=False)

    # Create HNSW index on PostgreSQL for fast vector cosine similarity search
    if is_postgres:
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_embedding_hnsw 
            ON jobs USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS idx_jobs_embedding_hnsw;")

    op.drop_constraint('fk_job_clusters_primary_job', 'job_clusters', type_='foreignkey')
    op.drop_constraint('fk_jobs_cluster_id', 'jobs', type_='foreignkey')
    op.drop_column('jobs', 'embedded_at')
    op.drop_column('jobs', 'embedding')
    op.drop_column('jobs', 'verification_error')
    op.drop_column('jobs', 'verified_at')
    op.drop_column('jobs', 'verification_status')
    op.drop_column('jobs', 'is_primary_in_cluster')
    op.drop_column('jobs', 'cluster_id')
    op.drop_table('job_clusters')
