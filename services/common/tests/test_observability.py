import asyncio
import io
import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from partner_observability import (JsonFormatter, RequestLogMiddleware, correlation_id,
                                   propagate_request_id, request_id)

@pytest.mark.parametrize('bad', ['', 'a'*65, 'x\ny', 'Тест', '../../x', 'token=secret', None])
def test_untrusted_correlation_ids_are_replaced(bad):
    value = correlation_id(bad)
    assert len(value) == 32
    assert value != bad


def test_formatter_redacts_credentials_and_exception_values():
    formatter = JsonFormatter('test')
    try:
        raise ValueError('private prompt and password=do-not-log')
    except ValueError:
        import sys
        record = logging.LogRecord('test', logging.ERROR, __file__, 1,
            'upstream.failed cookie=session-secret password=hidden', (), sys.exc_info())
    payload = json.loads(formatter.format(record))
    assert payload['error']['type'] == 'ValueError'
    assert payload['error']['frames'][-1]['function'] == 'test_formatter_redacts_credentials_and_exception_values'
    assert 'session-secret' not in json.dumps(payload)
    assert 'do-not-log' not in json.dumps(payload)
    assert payload['service'] == 'test'


def test_full_stream_lifetime_and_parallel_context_isolation(caplog):
    async def run():
        captured=[]
        async def app(scope, receive, send):
            scope['route'] = SimpleNamespace(path='/chat/{chat_id}')
            outgoing = httpx.Request('GET', 'http://rag')
            await propagate_request_id(outgoing)
            captured.append((scope['path'], outgoing.headers['X-Request-ID']))
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'a','more_body':True})
            await asyncio.sleep(.01)
            await send({'type':'http.response.body','body':b'bc','more_body':False})
        middleware=RequestLogMiddleware(app)
        async def one(identity):
            sent=[]
            async def send(msg): sent.append(msg)
            async def receive(): return {'type':'http.disconnect'}
            await middleware({'type':'http','method':'POST','path':'/private/'+identity,
                'query_string':b'password=private','headers':[(b'x-request-id',identity.encode())]}, receive, send)
            assert (b'x-request-id',identity.encode()) in sent[0]['headers']
        with caplog.at_level(logging.INFO, logger='partner.http'):
            await asyncio.gather(one('trace-a'),one('trace-b'))
        assert sorted(i for _,i in captured)==['trace-a','trace-b']
        assert request_id()=='-'
    asyncio.run(run())
    records=[r for r in caplog.records if r.getMessage()=='http.request']
    assert len(records)==2
    assert all(r.bytes_sent==3 and r.duration_ms>=8 and r.path=='/chat/{chat_id}' for r in records)


def test_exception_is_logged_and_context_reset(caplog):
    async def broken(scope, receive, send): raise RuntimeError('secret')
    async def send(msg): pass
    async def receive(): return {'type':'http.disconnect'}
    with caplog.at_level(logging.ERROR):
        asyncio.run(RequestLogMiddleware(broken)({'type':'http','method':'GET','path':'/x','headers':[]}, receive, send))
    assert caplog.records[-1].status==500
    assert caplog.records[-1].outcome=='failed'
    assert request_id()=='-'


def test_unhandled_error_response_has_trace_and_no_exception_message():
    async def run():
        sent=[]
        async def broken(scope,receive,send):raise ValueError('private-password')
        async def receive():return {'type':'http.disconnect'}
        async def send(msg):sent.append(msg)
        await RequestLogMiddleware(broken)({'type':'http','method':'GET','path':'/x','headers':[(b'x-request-id',b'error-trace')]},receive,send)
        assert sent[0]['status']==500 and (b'x-request-id',b'error-trace') in sent[0]['headers']
        assert b'private-password' not in sent[1]['body']
    asyncio.run(run())


def test_midstream_exception_propagates_instead_of_sending_second_headers():
    async def run():
        sent=[]
        async def broken(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            raise ValueError('private-password')
        async def receive():return {'type':'http.disconnect'}
        async def send(msg):sent.append(msg)
        with pytest.raises(ValueError):
            await RequestLogMiddleware(broken)({'type':'http','method':'GET','path':'/x','headers':[]},receive,send)
        assert len(sent)==1
    asyncio.run(run())
