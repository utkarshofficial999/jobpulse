"""milestone 3 matching outbox schema

Revision ID: 0003_milestone3
Revises: 0002_milestone2
Create Date: 2026-10-16 20:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = '0003_milestone3'
down_revision: Union[str, None] = '0002_milestone2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = (conn.dialect.name == "postgresql")

    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('telegram_chat_id', sa.String(length=64), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('alert_frequency', sa.String(length=32), nullable=False, server_default='daily_9am'),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
        sa.UniqueConstraint('telegram_chat_id', name='uq_users_telegram_chat_id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_users_telegram', 'users', ['telegram_chat_id'], unique=True)

    # 2. Candidate Profiles table
    op.create_table(
        'candidate_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('target_roles', sa.JSON(), nullable=False),
        sa.Column('target_seniorities', sa.JSON(), nullable=False),
        sa.Column('preferred_remote_types', sa.JSON(), nullable=False),
        sa.Column('preferred_locations', sa.JSON(), nullable=False),
        sa.Column('raw_resume_text', sa.Text(), nullable=True),
        sa.Column('parsed_skills', sa.JSON(), nullable=False),
        sa.Column('min_similarity_score', sa.Float(), nullable=False, server_default='0.65'),
        sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_candidate_profiles_user_id')
    )

    if is_postgres:
        op.add_column('candidate_profiles', sa.Column('profile_embedding', Vector(384), nullable=True))
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_candidate_embedding_hnsw 
            ON candidate_profiles USING hnsw (profile_embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """)
    else:
        op.add_column('candidate_profiles', sa.Column('profile_embedding', sa.JSON(), nullable=True))

    # 3. Job Feedback table
    op.create_table(
        'job_feedback',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('cluster_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['job_clusters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'job_id', 'action', name='uq_user_job_action')
    )
    op.create_index('idx_user_feedback_action', 'job_feedback', ['user_id', 'action'])
    op.create_index('idx_user_cluster_action', 'job_feedback', ['user_id', 'cluster_id', 'action'])

    # 4. Notification Outbox table
    op.create_table(
        'notification_outbox',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=512), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_outbox_pending', 'notification_outbox', ['status', 'next_retry_at'])


def downgrade() -> None:
    conn = op.get_bind()
    is_postgres = (conn.dialect.name == "postgresql")

    op.drop_table('notification_outbox')
    op.drop_table('job_feedback')

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS idx_candidate_embedding_hnsw;")

    op.drop_table('candidate_profiles')
    op.drop_table('users')
