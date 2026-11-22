import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID, uuid4

import anyio
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from partner_observability import RequestLogMiddleware, configure_logging, propagate_request_id

from .config import Settings
from .database import Conversation, Message, build_engine
from .rag_client import RagProtocolError, event, normalize_sources, read_events
from .schemas import AskRequest, CreateConversation
from .security import current_user
from .store import conversation_view, now_ms, owned_chat, persist_turn, prepare_turn, recover_expired

log = logging.getLogger(__name__)
User = Annotated[dict, Depends(current_user)]


class TurnCancelled(Exception):
    pass


def create_app(settings=None, *, transport=None):
    configure_logging("backend")
    settings = settings or Settings()
    if settings.history_turns < 0 or settings.history_max_chars < 0 or settings.generation_timeout <= 0:
        raise ValueError('Invalid history or timeout configuration')
    engine = build_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(application):
        async with httpx.AsyncClient(transport=transport, trust_env=False, event_hooks={'request': [propagate_request_id]}, timeout=httpx.Timeout(
            settings.generation_timeout, connect=5, pool=5), limits=httpx.Limits(
            max_connections=30, max_keepalive_connections=10)) as client:
            application.state.http = client
            yield
        await engine.dispose()

    application = FastAPI(title='Partner Agent Backend', version='2.0.0', lifespan=lifespan,
        docs_url='/api/v1/docs', openapi_url='/api/v1/openapi.json')
    application.state.settings = settings
    application.state.sessions = sessions

    @application.middleware('http')
    async def protect_requests(request: Request, call_next):
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') not in settings.allowed_origins:
                return JSONResponse({'detail': 'Источник запроса не разрешён'}, status_code=403)
            if request.headers.get('x-requested-with') != 'PartnerAgent':
                return JSONResponse({'detail': 'Необходим заголовок X-Requested-With'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    application.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
        allow_credentials=True, allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
        allow_headers=['Content-Type', 'X-CSRF-Token', 'X-Requested-With', 'X-Request-ID'], expose_headers=['X-Request-ID'])

    application.add_middleware(RequestLogMiddleware)

    @application.get('/health')
    async def health():
        async with sessions() as db:
            await db.execute(text('SELECT 1'))
        return {'status': 'ok'}

    @application.get('/api/v1/conversations')
    async def list_conversations(user: User, limit: Annotated[int, Query(ge=1, le=100)] = 100,
                                 offset: Annotated[int, Query(ge=0)] = 0):
        async with sessions() as db:
            chats = (await db.scalars(select(Conversation).where(Conversation.user_id == user['id'])
                .order_by(Conversation.updated_at.desc(), Conversation.id).limit(limit).offset(offset))).all()
            return [conversation_view(chat) for chat in chats]

    @application.post('/api/v1/conversations', status_code=201)
    async def create_conversation(body: CreateConversation, user: User):
        stamp = now_ms()
        chat = Conversation(id=str(uuid4()), user_id=user['id'], title=body.title,
                            created_at=stamp, updated_at=stamp, next_sequence=0)
        async with sessions.begin() as db:
            db.add(chat)
        return conversation_view(chat, [])

    @application.get('/api/v1/conversations/{chat_id}')
    async def get_conversation(chat_id: UUID, user: User):
        async with sessions.begin() as db:
            chat = await owned_chat(db, str(chat_id), user['id'], lock=True)
            await recover_expired(db, chat)
            messages = (await db.scalars(select(Message).where(Message.conversation_id == chat.id)
                .order_by(Message.sequence))).all()
            return conversation_view(chat, messages)

    @application.delete('/api/v1/conversations/{chat_id}', status_code=204)
    async def delete_conversation(chat_id: UUID, user: User):
        async with sessions.begin() as db:
            chat = await owned_chat(db, str(chat_id), user['id'], lock=True)
            await db.delete(chat)
        return Response(status_code=204)

    @application.post('/api/v1/conversations/{chat_id}/requests/{request_id}/cancel', status_code=204)
    async def cancel_request(chat_id: UUID, request_id: UUID, user: User):
        async with sessions.begin() as db:
            chat = await owned_chat(db, str(chat_id), user['id'], lock=True)
            message = await db.scalar(select(Message).where(Message.conversation_id == chat.id,
                Message.request_id == str(request_id), Message.role == 'assistant'))
            if message is None:
                raise HTTPException(404, 'Запрос не найден')
            if message.status == 'streaming':
                message.status = 'cancelled'
                message.error = 'Ответ остановлен'
                if chat.active_request_id == str(request_id):
                    chat.active_request_id = None
                    chat.lease_until = None
                chat.updated_at = now_ms()
        return Response(status_code=204)

    @application.get('/api/v1/documents')
    async def documents(user: User):
        try:
            response = await application.state.http.get(f'{settings.rag_url}/api/v1/documents')
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, 'Не удалось получить список документов') from None

    @application.post('/api/v1/ask')
    async def ask(body: AskRequest, user: User):
        turn = await prepare_turn(sessions, user['id'], body, settings)
        if turn.replayed:
            return {**turn.metadata(), 'answer': turn.content, 'sources': turn.sources}
        log.info('generation.started', extra={'generation_id': turn.request_id, 'conversation_id': turn.conversation_id})
        content, sources, status, error = '', [], 'error', 'Не удалось завершить ответ'
        try:
            async with asyncio.timeout(settings.generation_timeout):
                response = await application.state.http.post(f'{settings.rag_url}/api/v1/ask',
                    json={'question': body.question, 'history': turn.history})
                response.raise_for_status()
                payload = response.json()
                answer = payload['answer']
                if not isinstance(answer, str) or not answer.strip() or len(answer) > settings.max_answer_chars:
                    raise RagProtocolError('Invalid answer')
                normalized = normalize_sources(payload['sources'])
                content, sources = answer, normalized
                status, error = 'complete', None
        except asyncio.CancelledError:
            status, error = 'cancelled', 'Соединение прервано'
            raise
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError, RagProtocolError):
            log.warning('generation.upstream_failed', exc_info=True, extra={'generation_id': turn.request_id})
            raise HTTPException(502, 'RAG не смог завершить ответ. Повторите запрос') from None
        finally:
            with anyio.CancelScope(shield=True):
                saved = await persist_turn(sessions, turn, status, content, sources, error)
                log.info('generation.finished', extra={'generation_id': turn.request_id, 'outcome': status, 'answer_chars': len(content), 'sources_count': len(sources)})
        if not saved:
            raise HTTPException(409, 'Запрос остановлен или диалог удалён')
        return {**turn.metadata(), 'answer': content, 'sources': sources}

    @application.post('/api/v1/ask/stream')
    async def ask_stream(body: AskRequest, user: User):
        turn = await prepare_turn(sessions, user['id'], body, settings)

        async def generate():
            log.info('generation.started', extra={'generation_id': turn.request_id, 'replayed': turn.replayed})
            content, sources = '', []
            status, error = 'cancelled', 'Соединение прервано'
            checkpoint = time.monotonic()
            try:
                yield event('meta', turn.metadata())
                if turn.replayed:
                    yield event('sources', turn.sources)
                    yield event('token', {'text': turn.content})
                    yield event('done', turn.metadata())
                    return
                async with asyncio.timeout(settings.generation_timeout):
                    async with application.state.http.stream('POST', f'{settings.rag_url}/api/v1/ask/stream',
                            json={'question': body.question, 'history': turn.history}) as response:
                        response.raise_for_status()
                        if 'text/event-stream' not in response.headers.get('content-type', ''):
                            raise RagProtocolError('Invalid content type')
                        async for name, payload in read_events(response):
                            if name == 'sources':
                                sources = normalize_sources(payload)
                                if not await persist_turn(sessions, turn, 'streaming', content, sources):
                                    raise TurnCancelled()
                                yield event('sources', sources)
                            elif name == 'token':
                                if not isinstance(payload, dict) or not isinstance(payload.get('text'), str):
                                    raise RagProtocolError('Invalid token')
                                content += payload['text']
                                if len(content) > settings.max_answer_chars:
                                    raise RagProtocolError('Answer too large')
                                if time.monotonic() - checkpoint >= 0.5:
                                    if not await persist_turn(sessions, turn, 'streaming', content, sources):
                                        raise TurnCancelled()
                                    checkpoint = time.monotonic()
                                yield event('token', {'text': payload['text']})
                            elif name == 'error':
                                raise RagProtocolError('RAG reported an error')
                            elif name == 'done':
                                if not content.strip():
                                    raise RagProtocolError('Empty answer')
                                status, error = 'complete', None
                                if not await persist_turn(sessions, turn, status, content, sources):
                                    raise TurnCancelled()
                                yield event('done', turn.metadata())
                                return
                        raise RagProtocolError('RAG stream ended without done')
            except TurnCancelled:
                status, error = 'cancelled', 'Ответ остановлен'
                yield event('error', {'detail': error})
            except (httpx.HTTPError, TimeoutError, ValueError, TypeError, RagProtocolError):
                status, error = 'error', 'Не удалось завершить ответ. Повторите запрос'
                log.warning('generation.stream_failed', exc_info=True, extra={'generation_id': turn.request_id})
                yield event('error', {'detail': error})
            finally:
                if not turn.replayed:
                    with anyio.CancelScope(shield=True):
                        await persist_turn(sessions, turn, status, content, sources, error)
                log.info('generation.finished', extra={'generation_id': turn.request_id, 'outcome': 'replayed' if turn.replayed else status, 'answer_chars': len(content), 'sources_count': len(sources)})

        return StreamingResponse(generate(), media_type='text/event-stream', headers={
            'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    return application


app = create_app()
