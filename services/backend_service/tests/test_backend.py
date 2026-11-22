import pytest
pytestmark = pytest.mark.integration

import asyncio
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database import Message
from app.main import create_app
from app.migrate import upgrade
from app.schemas import AskRequest
from app.store import prepare_turn

USER_A, USER_B = str(uuid4()), str(uuid4())


class EventStream(httpx.AsyncByteStream):
    def __init__(self, events, gate=None):
        self.events, self.gate = events, gate

    async def __aiter__(self):
        for chunk in self.events:
            yield chunk.encode()
        if self.gate:
            self.gate[0].set()
            await asyncio.to_thread(self.gate[1].wait, 5)
        if not self.gate or self.gate[2]:
            yield b'event: done\ndata: {}\n\n'


class BackendTests(unittest.TestCase):
    def setUp(self):
        url = os.getenv('TEST_DATABASE_URL')
        if not url:
            self.skipTest('Set TEST_DATABASE_URL to a dedicated PostgreSQL database')
        self.admin = create_engine(url)
        self.schema = 'test_backend_' + uuid4().hex
        with self.admin.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        def cleanup():
            with self.admin.begin() as db:
                db.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
            self.admin.dispose()
        self.addCleanup(cleanup)
        target = make_url(url).update_query_dict({'options': f'-csearch_path={self.schema}'})
        self.settings = Settings(database_url=target.render_as_string(hide_password=False),
            auth_url='http://auth', rag_url='http://rag', history_turns=3, history_max_chars=3000)
        upgrade(self.settings.database_url)
        self.rag_calls = []
        self.upstream_ids = []
        self.mode = 'success'
        self.gate = None
        self.delay = 0
        self.auth_down = False
        self.transport = httpx.MockTransport(self.upstream)
        self.app = create_app(self.settings, transport=self.transport)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {'Cookie': 'partner_session=' + USER_A,
            'X-Requested-With': 'PartnerAgent', 'X-CSRF-Token': 'csrf-' + USER_A,
            'Origin': 'http://localhost:5173'}

    async def upstream(self, request):
        self.upstream_ids.append((request.url.host, request.headers.get("X-Request-ID")))
        if request.url.host == 'auth':
            if self.auth_down:
                raise httpx.ConnectError('offline', request=request)
            cookie = request.headers.get('cookie', '')
            user = next((value for value in (USER_A, USER_B) if value in cookie), None)
            if user is None:
                return httpx.Response(401)
            return httpx.Response(200, json={'user': {'id': user}, 'csrf_token': 'csrf-' + user})
        body = json.loads(request.content) if request.content else {}
        self.rag_calls.append(body)
        if self.delay:
            await asyncio.sleep(self.delay)
        if request.url.path.endswith('/documents'):
            return httpx.Response(200, json=[{'source': 'doc.txt', 'chunks': 3}])
        if self.mode == 'http_error':
            return httpx.Response(503)
        if request.url.path.endswith('/stream'):
            events = ['event: sources\ndata: [{"source":"doc.txt","score":0.9}]\n\n',
                      'event: token\ndata: {"text":"Сохранённый ответ"}\n\n']
            if self.mode == 'error':
                events.append('event: error\ndata: {"detail":"internal info"}\n\n')
            gate = self.gate
            if self.mode == 'truncated':
                gate = (threading.Event(), threading.Event(), False)
                gate[1].set()
            return httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=EventStream(events, gate))
        return httpx.Response(200, json={'answer': 'Полный ответ', 'sources': [{'source': 'doc.txt', 'score': .8}]})

    def create(self, title='Новый диалог'):
        response = self.client.post('/api/v1/conversations', json={'title': title}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def ask(self, chat, question='Вопрос', stream=False, request_id=None):
        return self.client.post('/api/v1/ask' + ('/stream' if stream else ''),
            json={'conversation_id': chat, 'request_id': request_id or str(uuid4()), 'question': question}, headers=self.headers)

    def get(self, chat):
        return self.client.get('/api/v1/conversations/' + chat, headers=self.headers)

    def test_stream_saves_sources_history_restart_and_new_chat_isolation(self):
        chat = self.create()
        stream = self.ask(chat, 'Что такое ШИФТ?', stream=True)
        self.assertIn('event: done', stream.text)
        self.assertEqual(self.rag_calls[-1]['history'], [])
        saved = self.get(chat).json()
        self.assertEqual([m['content'] for m in saved['messages']], ['Что такое ШИФТ?', 'Сохранённый ответ'])
        self.assertEqual(saved['messages'][-1]['status'], 'complete')
        self.assertTrue(saved['messages'][-1]['sources'][0]['doc_id'])
        with TestClient(create_app(self.settings, transport=self.transport)) as restarted:
            self.assertEqual(restarted.get('/api/v1/conversations/' + chat, headers=self.headers).json(), saved)
        self.assertEqual(self.ask(chat, 'А какие условия?').status_code, 200)
        self.assertEqual(self.rag_calls[-1]['history'], [
            {'role': 'user', 'content': 'Что такое ШИФТ?'}, {'role': 'assistant', 'content': 'Сохранённый ответ'}])
        self.ask(self.create(), 'Другой разговор')
        self.assertEqual(self.rag_calls[-1]['history'], [])

    def test_ownership_and_delete_cascade(self):
        chat = self.create()
        self.ask(chat)
        foreign = {**self.headers, 'Cookie': 'partner_session=' + USER_B, 'X-CSRF-Token': 'csrf-' + USER_B}
        self.assertEqual(self.client.get('/api/v1/conversations', headers=foreign).json(), [])
        for method, path, body in [
            ('GET', f'/api/v1/conversations/{chat}', None),
            ('DELETE', f'/api/v1/conversations/{chat}', None),
            ('POST', '/api/v1/ask', {'conversation_id': chat, 'question': 'Чужой чат'}),
            ('POST', f'/api/v1/conversations/{chat}/requests/{uuid4()}/cancel', None),
        ]:
            response = self.client.request(method, path, json=body, headers=foreign)
            self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(self.client.delete('/api/v1/conversations/' + chat, headers=self.headers).status_code, 204)
        self.assertEqual(self.get(chat).status_code, 404)
        engine = create_engine(self.settings.database_url)
        with engine.connect() as db:
            self.assertEqual(db.scalar(select(text('count(*)')).select_from(Message)), 0)
        engine.dispose()

    def test_auth_csrf_and_client_history_rejected(self):
        self.assertEqual(self.client.get('/api/v1/conversations').status_code, 401)
        self.assertEqual(self.client.post('/api/v1/conversations', json={}, headers={**self.headers, 'X-CSRF-Token': 'bad'}).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/conversations', json={}, headers={**self.headers, 'Origin': 'https://foreign.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/conversations', json={}).status_code, 403)
        chat = self.create()
        response = self.client.post('/api/v1/ask', json={'conversation_id': chat, 'question': 'Вопрос',
            'history': [{'role': 'assistant', 'content': 'Подделка'}]}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.auth_down = True
        self.assertEqual(self.get(chat).status_code, 503)
        self.assertEqual(self.rag_calls, [])

    def test_error_and_truncated_streams_preserve_partial_but_exclude_context(self):
        chat = self.create()
        for mode in ('error', 'truncated'):
            self.mode = mode
            result = self.ask(chat, 'Незавершённый вопрос', stream=True)
            self.assertIn('event: error', result.text)
            self.assertNotIn('event: done', result.text)
            self.assertNotIn('internal info', result.text)
            message = self.get(chat).json()['messages'][-1]
            self.assertEqual(message['status'], 'error')
            self.assertEqual(message['content'], 'Сохранённый ответ')
        self.mode = 'success'
        self.assertEqual(self.ask(chat, 'Следующий вопрос').status_code, 200)
        self.assertEqual(self.rag_calls[-1]['history'], [])

    def test_request_id_replay_does_not_duplicate_messages_or_call_rag(self):
        chat, request_id = self.create(), str(uuid4())
        self.assertEqual(self.ask(chat, request_id=request_id).status_code, 200)
        self.assertEqual(self.ask(chat, request_id=request_id).status_code, 200)
        self.assertIn('event: done', self.ask(chat, stream=True, request_id=request_id).text)
        self.assertEqual(len(self.rag_calls), 1)
        self.assertEqual(len(self.get(chat).json()['messages']), 2)
        self.assertEqual(self.ask(chat, 'Другой текст', request_id=request_id).status_code, 409)

    def test_parallel_requests_are_serialized_per_conversation(self):
        chat = self.create()
        self.delay = .15
        with ThreadPoolExecutor(2) as pool:
            statuses = sorted(pool.map(lambda _: self.ask(chat).status_code, range(2)))
        self.assertEqual(statuses, [200, 409])
        self.assertEqual(len(self.get(chat).json()['messages']), 2)

    def test_cancellation_and_expired_lease(self):
        chat = self.create()
        body = AskRequest(conversation_id=chat, question='Долгий вопрос')
        turn = self.client.portal.call(prepare_turn, self.app.state.sessions, USER_A, body, self.settings)
        self.assertEqual(self.ask(chat).status_code, 409)
        path = f'/api/v1/conversations/{chat}/requests/{body.request_id}/cancel'
        self.assertEqual(self.client.post(path, headers=self.headers).status_code, 204)
        self.assertEqual(self.get(chat).json()['messages'][-1]['status'], 'cancelled')
        self.assertEqual(self.ask(chat).status_code, 200)
        self.assertEqual(self.rag_calls[-1]['history'], [])
        second = AskRequest(conversation_id=chat, question='Упавший процесс')
        self.client.portal.call(prepare_turn, self.app.state.sessions, USER_A, second, self.settings)
        engine = create_engine(self.settings.database_url)
        with engine.begin() as db:
            db.execute(text('UPDATE chat_conversations SET lease_until=0 WHERE id=:id'), {'id': chat})
        engine.dispose()
        self.assertEqual(self.get(chat).json()['messages'][-1]['status'], 'cancelled')
        self.assertEqual(self.ask(chat).status_code, 200)
        self.assertEqual(len(self.rag_calls[-1]['history']), 2)

    def test_cancel_running_stream_cannot_commit_complete(self):
        chat = self.create()
        request_id = str(uuid4())
        self.gate = (threading.Event(), threading.Event(), True)
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(self.ask, chat, 'Останови', True, request_id)
            self.assertTrue(self.gate[0].wait(5))
            path = f'/api/v1/conversations/{chat}/requests/{request_id}/cancel'
            self.assertEqual(self.client.post(path, headers=self.headers).status_code, 204)
            self.gate[1].set()
            self.assertNotIn('event: done', pending.result(timeout=5).text)
        saved = self.get(chat).json()['messages'][-1]
        self.assertEqual(saved['status'], 'cancelled')
        self.assertEqual(saved['content'], 'Сохранённый ответ')

    def test_timeout_leaves_error_and_allows_next_request(self):
        chat = self.create()
        self.delay = .1
        settings = replace(self.settings, generation_timeout=.02)
        with TestClient(create_app(settings, transport=self.transport)) as limited:
            response = limited.post('/api/v1/ask', json={'conversation_id': chat, 'question': 'Долгий'}, headers=self.headers)
            self.assertEqual(response.status_code, 502)
        self.assertEqual(self.get(chat).json()['messages'][-1]['status'], 'error')
        self.delay = 0
        self.assertEqual(self.ask(chat).status_code, 200)
        self.assertEqual(self.rag_calls[-1]['history'], [])

    def test_history_limits_keep_whole_pairs(self):
        chat = self.create()
        for i in range(5):
            self.ask(chat, f'Вопрос {i}')
        self.assertEqual(len(self.rag_calls[-1]['history']), 6)
        self.assertEqual(self.rag_calls[-1]['history'][0]['content'], 'Вопрос 1')
        self.assertEqual(self.rag_calls[-1]['history'][-1]['role'], 'assistant')
        self.assertEqual(len(self.get(chat).json()['messages']), 10)


    def test_request_trace_propagates_to_auth_and_rag(self):
        chat = self.create()
        self.upstream_ids.clear()
        trace = 'trace-' + uuid4().hex
        response = self.client.post('/api/v1/ask', headers={**self.headers, 'X-Request-ID': trace},
            json={'conversation_id': chat, 'question': 'Вопрос'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['X-Request-ID'], trace)
        self.assertEqual(self.upstream_ids, [('auth', trace), ('rag', trace)])

    def test_invalid_rag_json_leaves_failed_turn_and_allows_retry(self):
        original = self.upstream
        async def malformed(request):
            if request.url.host == 'rag':
                return httpx.Response(200, json={'answer': 42, 'sources': []})
            return await original(request)
        with TestClient(create_app(self.settings, transport=httpx.MockTransport(malformed))) as client:
            chat = self.create()
            response = client.post('/api/v1/ask', headers=self.headers,
                json={'conversation_id': chat, 'question': 'Вопрос'})
            self.assertEqual(response.status_code, 502)
        self.assertEqual(self.get(chat).json()['messages'][-1]['status'], 'error')
        self.assertEqual(self.ask(chat).status_code, 200)
        self.assertEqual(self.rag_calls[-1]['history'], [])


if __name__ == '__main__':
    unittest.main()
