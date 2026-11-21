"""Durable conversations, messages and generation state."""
from alembic import op
import sqlalchemy as sa

revision = 'backend_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chat_conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('next_sequence', sa.Integer(), nullable=False),
        sa.Column('active_request_id', sa.String(36)),
        sa.Column('lease_until', sa.BigInteger()))
    op.create_index('ix_chat_conversations_user_id', 'chat_conversations', ['user_id'])
    op.create_index('ix_chat_conversations_updated_at', 'chat_conversations', ['updated_at'])
    op.create_table('chat_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('error', sa.Text()),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.UniqueConstraint('conversation_id', 'sequence', name='uq_chat_message_sequence'),
        sa.UniqueConstraint('conversation_id', 'request_id', 'role', name='uq_chat_request_role'),
        sa.CheckConstraint("role IN ('user', 'assistant')", name='ck_chat_message_role'),
        sa.CheckConstraint("status IN ('complete', 'streaming', 'error', 'cancelled')", name='ck_chat_message_status'))
    op.create_index('ix_chat_messages_conversation_sequence', 'chat_messages', ['conversation_id', 'sequence'])


def downgrade():
    op.drop_table('chat_messages')
    op.drop_table('chat_conversations')
