import asyncio
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from app import main
from app.schemas import DocumentInfo, ReindexResponse, SourceChunk

pytestmark=pytest.mark.contract

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main,'ensure_collection',lambda:None)
    monkeypatch.setattr(main.settings,'admin_token','test-admin-secret')
    main.reindex_lock=asyncio.Lock()
    with TestClient(main.app,raise_server_exceptions=False) as client:
        yield client

@pytest.mark.parametrize('method,path', [('GET','files'),('POST','files'),('DELETE','files?source=x.md'),('POST','reindex')])
def test_admin_requires_token(client,method,path):
    assert client.request(method,'/api/v1/admin/'+path).status_code==401


def test_admin_page_and_files_inventory(client,monkeypatch):
    monkeypatch.setattr(main,'list_storage_files',lambda:[])
    assert client.get('/admin').status_code==200
    assert client.get('/api/v1/admin/files',headers={'X-Admin-Token':'test-admin-secret'}).json()==[]


def test_admin_upload_contract(client,monkeypatch):
    save=Mock(return_value=DocumentInfo(category='school',source='school/go.md',chunks=2))
    monkeypatch.setattr(main,'save_and_index_file',save)
    response=client.post('/api/v1/admin/files',headers={'X-Admin-Token':'test-admin-secret'},data={'category':'school'},files=[('files',('go.md',b'# Go','text/markdown'))])
    assert response.status_code==200
    assert response.json()['total_chunks_added']==2
    save.assert_called_once_with('go.md',b'# Go','school')


def test_upload_error_does_not_leak_exception_and_releases_lock(client,monkeypatch):
    monkeypatch.setattr(main,'save_and_index_file',Mock(side_effect=RuntimeError('postgres://password@private-host')))
    response=client.post('/api/v1/admin/files',headers={'X-Admin-Token':'test-admin-secret'},files=[('files',('go.md',b'text'))])
    assert response.status_code==502 and 'private-host' not in response.text
    assert not main.reindex_lock.locked()


def test_reindex_mutual_exclusion(client):
    client.portal.call(main.reindex_lock.acquire)
    try:
        assert client.post('/api/v1/admin/reindex',headers={'X-Admin-Token':'test-admin-secret'}).status_code==409
    finally: main.reindex_lock.release()


def test_delete_and_reindex_contract(client,monkeypatch):
    delete=Mock();monkeypatch.setattr(main,'delete_file_and_vectors',delete)
    headers={'X-Admin-Token':'test-admin-secret'}
    assert client.delete('/api/v1/admin/files?source=school/go.md',headers=headers).json()=={'deleted':'school/go.md'}
    delete.assert_called_once_with('school/go.md')
    monkeypatch.setattr(main,'index_dataset',lambda:ReindexResponse(folders_found=1,files_indexed=1,total_chunks=2,files=[]))
    assert client.post('/api/v1/admin/reindex',headers=headers).json()['total_chunks']==2


def test_stream_setup_failure_returns_502(client,monkeypatch):
    async def broken(*a): raise RuntimeError('secret')
    monkeypatch.setattr(main,'stream_answer',broken)
    response=client.post('/api/v1/ask/stream',json={'question':'Go','history':[]})
    assert response.status_code==502 and 'secret' not in response.text


def test_stream_error_is_terminal_and_sanitized(client,monkeypatch):
    async def broken(*a):
        async def tokens():
            yield 'Часть ответа'
            raise RuntimeError('private-token')
        return [],tokens()
    monkeypatch.setattr(main,'stream_answer',broken)
    response=client.post('/api/v1/ask/stream',json={'question':'Go','history':[]},headers={'X-Request-ID':'trace-rag-error'})
    assert response.status_code==200
    assert response.headers['X-Request-ID']=='trace-rag-error'
    assert 'event: error' in response.text and 'event: done' not in response.text
    assert 'private-token' not in response.text


def test_sources_are_sent_after_tokens_and_before_done(client,monkeypatch):
    async def answer(*a):
        async def tokens(): yield 'Ответ'
        return [SourceChunk(category='go',source='Курс Go',score=.9)],tokens()
    monkeypatch.setattr(main,'stream_answer',answer)
    response=client.post('/api/v1/ask/stream',json={'question':'Go','history':[]})
    assert response.text.index('event: token')<response.text.index('event: sources')<response.text.index('event: done')
    assert response.headers['X-Accel-Buffering']=='no'


def test_admin_logs_require_token_and_validate_filters(client):
    assert client.get('/api/v1/admin/logs').status_code == 401
    headers = {'X-Admin-Token': 'test-admin-secret'}
    for query in ('service=../../etc/passwd', 'level=UNKNOWN', 'limit=1001', 'limit=0', 'search=' + 'x' * 201):
        assert client.get('/api/v1/admin/logs?' + query, headers=headers).status_code == 422


def test_admin_logs_are_filtered_sorted_and_not_cached(client, monkeypatch, tmp_path):
    import json
    monkeypatch.setenv('LOG_DIR', str(tmp_path))
    records = [
        {'timestamp': '2026-11-22T12:00:00.000+00:00', 'service': 'backend', 'level': 'INFO', 'event': 'http.request'},
        {'timestamp': '2026-11-22T12:00:01.000+00:00', 'service': 'backend', 'level': 'ERROR', 'event': 'generation.failed', 'request_id': 'trace-42'},
    ]
    (tmp_path/'backend.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in records))
    response = client.get('/api/v1/admin/logs?service=backend&level=ERROR&search=trace-42', headers={'X-Admin-Token': 'test-admin-secret'})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['entries'] == [records[1]]


def test_admin_log_read_failures_are_sanitized(client, monkeypatch):
    monkeypatch.setattr(main, 'read_recent_logs', Mock(side_effect=PermissionError('/private/directory')))
    response = client.get('/api/v1/admin/logs', headers={'X-Admin-Token': 'test-admin-secret'})
    assert response.status_code == 503
    assert 'private' not in response.text
