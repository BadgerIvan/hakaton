"""Initial PostgreSQL schema for authentication."""
from alembic import op
import sqlalchemy as sa

revision = 'auth_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('password_hash', sa.String(512), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False))
    op.create_index('ix_auth_users_email', 'auth_users', ['email'], unique=True)
    op.create_table('auth_sessions',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('auth_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('csrf_token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])
    op.create_table('auth_rate_limits',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False))
    op.create_index('ix_auth_rate_limits_expires_at', 'auth_rate_limits', ['expires_at'])


def downgrade():
    op.drop_table('auth_rate_limits')
    op.drop_table('auth_sessions')
    op.drop_table('auth_users')
