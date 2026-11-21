import time
from dataclasses import dataclass
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import aliased
from .database import Conversation, Message


def now_ms():
    return int(time.time() * 1000)


def message_view(message):
    return {key: getattr(message, key) for key in ('id', 'role', 'content', 'sources', 'status', 'error', 'request_id')}


def conversation_view(chat, messages=None):
    result = {'id': chat.id, 'title': chat.title, 'updatedAt': chat.updated_at}
    if messages is not None:
        result['messages'] = [message_view(message) for message in messages]
    return result


async def owned_chat(db, chat_id, user_id, *, lock=False):
    query = select(Conversation).where(Conversation.id == chat_id, Conversation.user_id == user_id)
    if lock:
        query = query.with_for_update()
    chat = await db.scalar(query)
    if chat is None:
        raise HTTPException(404, 'Диалог не найден')
    return chat


async def recover_expired(db, chat):
    if chat.active_request_id and (chat.lease_until or 0) <= now_ms():
        message = await db.scalar(select(Message).where(
            Message.conversation_id == chat.id, Message.request_id == chat.active_request_id,
            Message.role == 'assistant', Message.status == 'streaming'))
        if message:
            message.status = 'cancelled'
            message.error = 'Генерация прервана. Повторите запрос'
        chat.active_request_id = None
        chat.lease_until = None


@dataclass
class Turn:
    conversation_id: str
    request_id: str
    user_message_id: str
    assistant_message_id: str
    history: list[dict]
    content: str = ''
    sources: list | None = None
    replayed: bool = False

    def metadata(self):
        return {key: getattr(self, key) for key in (
            'conversation_id', 'request_id', 'user_message_id', 'assistant_message_id')}


async def prepare_turn(sessions, user_id, body, settings):
    chat_id, request_id = str(body.conversation_id), str(body.request_id)
    async with sessions.begin() as db:
        chat = await owned_chat(db, chat_id, user_id, lock=True)
        await recover_expired(db, chat)
        existing = list((await db.scalars(select(Message).where(
            Message.conversation_id == chat_id, Message.request_id == request_id
        ).order_by(Message.sequence))).all())
        if existing:
            if len(existing) == 2 and existing[0].content == body.question and existing[1].status == 'complete':
                return Turn(chat_id, request_id, existing[0].id, existing[1].id, [],
                            existing[1].content, existing[1].sources, True)
            raise HTTPException(409, 'Запрос уже принят. Обновите диалог или используйте новый request_id')
        if chat.active_request_id:
            raise HTTPException(409, 'В этом диалоге уже готовится ответ')
        # Join pairs before applying LIMIT so failed/orphaned questions cannot hide older context.
        question_row, answer_row = aliased(Message), aliased(Message)
        pairs = list((await db.execute(select(question_row, answer_row).join(answer_row,
            (answer_row.conversation_id == question_row.conversation_id) &
            (answer_row.request_id == question_row.request_id) & (answer_row.role == 'assistant')
        ).where(question_row.conversation_id == chat_id, question_row.role == 'user',
            question_row.status == 'complete', answer_row.status == 'complete'
        ).order_by(question_row.sequence.desc()).limit(settings.history_turns))).all())
        pairs.reverse()
        history, size = [], 0
        for question, answer in reversed(pairs[-settings.history_turns:] if settings.history_turns else []):
            pair_size = len(question.content) + len(answer.content)
            if size + pair_size > settings.history_max_chars:
                break
            history[0:0] = [{'role': question.role, 'content': question.content},
                            {'role': answer.role, 'content': answer.content}]
            size += pair_size
        stamp = now_ms()
        user_message = Message(id=str(uuid4()), conversation_id=chat_id, request_id=request_id,
            sequence=chat.next_sequence, role='user', content=body.question,
            sources=[], status='complete', created_at=stamp)
        assistant = Message(id=str(uuid4()), conversation_id=chat_id, request_id=request_id,
            sequence=chat.next_sequence + 1, role='assistant', content='',
            sources=[], status='streaming', created_at=stamp)
        db.add_all([user_message, assistant])
        if chat.next_sequence == 0:
            chat.title = body.question[:62]
        chat.next_sequence += 2
        chat.updated_at = stamp
        chat.active_request_id = request_id
        chat.lease_until = stamp + int((settings.generation_timeout + 30) * 1000)
        return Turn(chat_id, request_id, user_message.id, assistant.id, history)


async def persist_turn(sessions, turn, status, content, sources, error=None):
    async with sessions.begin() as db:
        chat = await db.scalar(select(Conversation).where(
            Conversation.id == turn.conversation_id).with_for_update())
        if chat is None:
            return False  # The owner deleted the conversation while it was streaming.
        message = await db.get(Message, turn.assistant_message_id)
        if message is None:
            return False
        if message.status == 'cancelled':
            # Preserve text already received when cancellation won the race with the last checkpoint.
            if len(content) > len(message.content):
                message.content = content
                message.sources = sources
            return False
        if message.status != 'streaming':
            return False  # Another worker already finalized this turn.
        message.content = content
        message.sources = sources
        message.status = status
        message.error = error
        chat.updated_at = now_ms()
        if status != 'streaming' and chat.active_request_id == turn.request_id:
            chat.active_request_id = None
            chat.lease_until = None
        return True
