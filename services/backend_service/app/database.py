from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = 'chat_conversations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Identity comes exclusively from auth /me, never from the request body.
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger, index=True)
    next_sequence: Mapped[int] = mapped_column(Integer, default=0)
    active_request_id: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[int | None] = mapped_column(BigInteger)


class Message(Base):
    __tablename__ = 'chat_messages'
    __table_args__ = (
        UniqueConstraint('conversation_id', 'sequence', name='uq_chat_message_sequence'),
        UniqueConstraint('conversation_id', 'request_id', 'role', name='uq_chat_request_role'),
        CheckConstraint("role IN ('user', 'assistant')", name='ck_chat_message_role'),
        CheckConstraint("status IN ('complete', 'streaming', 'error', 'cancelled')", name='ck_chat_message_status'),
        Index('ix_chat_messages_conversation_sequence', 'conversation_id', 'sequence'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('chat_conversations.id', ondelete='CASCADE'))
    request_id: Mapped[str] = mapped_column(String(36))
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default='')
    sources: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger)


def build_engine(url: str):
    if make_url(url).get_backend_name() != 'postgresql':
        raise ValueError('Backend requires PostgreSQL in DATABASE_URL')
    return create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
