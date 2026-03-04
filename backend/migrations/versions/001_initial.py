"""Initial schema — users and documents tables

Revision ID: 001
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('requests_today', sa.Integer(), default=0),
        sa.Column('last_request_date', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_api_key', 'users', ['api_key'], unique=True)

    # Request logs table
    op.create_table(
        'request_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('question', sa.Text(), nullable=True),
        sa.Column('query_type', sa.String(20), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('chunks_used', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('request_logs')
    op.drop_index('ix_users_api_key', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
