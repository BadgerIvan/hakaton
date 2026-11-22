from dataclasses import replace
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

pytestmark=pytest.mark.contract

@pytest.mark.parametrize('status,payload,expected',[
    (401,{},401),(500,{},503),(200,{},503),(200,{'user':{'id':None},'csrf_token':'x'},503),
    (200,{'user':{'id':'u'}},503)])
def test_auth_contract_fails_closed_without_touching_history(status,payload,expected):
    transport=httpx.MockTransport(lambda _:httpx.Response(status,json=payload))
    with TestClient(create_app(Settings(),transport=transport)) as client:
        response=client.get('/api/v1/conversations')
        assert response.status_code==expected
        assert response.headers['X-Request-ID']


def test_auth_connection_error_is_503():
    def offline(request):raise httpx.ConnectError('private-host',request=request)
    with TestClient(create_app(Settings(),transport=httpx.MockTransport(offline))) as client:
        response=client.get('/api/v1/conversations')
        assert response.status_code==503 and 'private-host' not in response.text


def test_invalid_configuration_rejected():
    for settings in (replace(Settings(),history_turns=-1),replace(Settings(),generation_timeout=0)):
        with pytest.raises(ValueError):create_app(settings)
