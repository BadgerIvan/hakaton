"""Real HTTP -> auth/backend/RAG -> PostgreSQL/Qdrant; model protocol is stubbed."""
import os
from uuid import uuid4
import httpx
import pytest

pytestmark=pytest.mark.integration
BASE=os.getenv('TEST_BASE_URL')
pytestmark=[pytest.mark.integration,pytest.mark.skipif(not BASE,reason='Set TEST_BASE_URL to the isolated test stack')]
ADMIN=os.getenv('TEST_ADMIN_TOKEN','local-test-admin')
HEADERS={'X-Requested-With':'PartnerAgent'}

@pytest.fixture
def client():
    with httpx.Client(base_url=BASE,timeout=30,trust_env=False) as client:yield client

def register(client):
    account={'name':'Тест','email':uuid4().hex+'@example.com','password':'test-password-123'}
    response=client.post('/api/v1/auth/register',json=account,headers=HEADERS)
    assert response.status_code==201,response.text
    return {**HEADERS,'X-CSRF-Token':response.json()['csrf_token']}

def seed(client):
    response=client.post('/api/v1/admin/files',headers={'X-Admin-Token':ADMIN},data={'category':'tests'},
        files=[('files',('go.md','---\ntitle: Курс Go\nsource_url: https://education.cft.ru/go\n---\n# Go\nКурс Go длится 12 недель. Обучение онлайн.'.encode(),'text/markdown'))])
    assert response.status_code==200,response.text
    return response.json()['uploaded'][0]['source']


def test_end_to_end_registration_index_stream_memory_history_logout(client):
    headers=register(client);source=seed(client)
    chat=client.post('/api/v1/conversations',headers=headers,json={}).json()['id']
    trace='system-'+uuid4().hex
    body={'conversation_id':chat,'request_id':str(uuid4()),'question':'Хочу изучать Go'}
    response=client.post('/api/v1/ask/stream',headers={**headers,'X-Request-ID':trace},json=body)
    assert response.status_code==200 and 'event: done' in response.text,response.text
    assert response.headers['X-Request-ID']==trace
    assert 'Курс' in response.text and 'Курс Go' in response.text
    follow=client.post('/api/v1/ask',headers=headers,json={'conversation_id':chat,'question':'Что я выбрал?'} )
    assert follow.status_code==200,follow.text
    assert 'Вы выбрали Go' in follow.json()['answer']
    saved=client.get('/api/v1/conversations/'+chat).json()
    assert len(saved['messages'])==4 and saved['messages'][-1]['status']=='complete'
    assert saved['messages'][-1]['sources'][0]['url']=='https://education.cft.ru/go'
    replay=client.post('/api/v1/ask/stream',headers=headers,json=body)
    assert 'event: done' in replay.text
    assert len(client.get('/api/v1/conversations/'+chat).json()['messages'])==4
    with httpx.Client(base_url=BASE,trust_env=False) as other:
        register(other)
        assert other.get('/api/v1/conversations/'+chat).status_code==404
    assert client.post('/api/v1/auth/logout',headers=headers).status_code==204
    assert client.get('/api/v1/conversations/'+chat).status_code==401
    # Cleanup only the fixture document via the admin API.
    assert client.delete('/api/v1/admin/files',params={'source':source},headers={'X-Admin-Token':ADMIN}).status_code==200


def test_proxy_security_and_admin_auth(client):
    assert client.get('/api/v1/admin/files').status_code==401
    headers=register(client)
    assert client.post('/api/v1/conversations',headers=HEADERS,json={}).status_code==403
    assert client.post('/api/v1/conversations',headers={**headers,'Origin':'https://foreign.example'},json={}).status_code==403
    response=client.get('/api/v1/conversations',headers={'X-Request-ID':'../../bad'})
    assert response.status_code==200
    assert response.headers['X-Request-ID']!='../../bad'


def test_frontend_assets_and_security_headers(client):
    import re
    response=client.get('/')
    assert response.status_code==200 and 'text/html' in response.headers['content-type']
    assert response.headers['X-Content-Type-Options']=='nosniff'
    match=re.search(r'src="(/assets/[^" ]+\.js)"',response.text)
    assert match
    asset=client.get(match.group(1))
    assert asset.status_code==200 and 'javascript' in asset.headers['content-type']
    assert client.get('/admin/').status_code==301
    assert client.get('/admin').status_code==200
