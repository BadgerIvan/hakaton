import asyncio
import json
from uuid import uuid4
import httpx
import pytest
from pydantic import ValidationError
from app.database import build_engine
from app.rag_client import RagProtocolError, event, normalize_sources, read_events
from app.schemas import AskRequest, CreateConversation

@pytest.mark.parametrize('question',['','   ','x'*4001])
def test_invalid_question(question):
    with pytest.raises(ValidationError): AskRequest(conversation_id=uuid4(),question=question)

@pytest.mark.parametrize('extra', [{'history':[]},{'user_id':'forged'}])
def test_client_cannot_supply_identity_or_history(extra):
    with pytest.raises(ValidationError): AskRequest(conversation_id=uuid4(),question='Hi',**extra)


def test_schema_normalization_and_new_request_ids():
    a=AskRequest(conversation_id=uuid4(),question='  Вопрос  ')
    b=AskRequest(conversation_id=a.conversation_id,question='Вопрос')
    assert a.question=='Вопрос' and a.request_id!=b.request_id
    assert CreateConversation(title='  Test  ').title=='Test'
    with pytest.raises(ValidationError): CreateConversation(title='   ')
    with pytest.raises(ValueError): build_engine('sqlite:///history.db')

@pytest.mark.parametrize('bad',[None,{},'x',[None],[{}],[{'source':4}]])
def test_invalid_sources(bad):
    with pytest.raises(RagProtocolError): normalize_sources(bad)


def test_sources_have_stable_ids_and_only_allowed_fields():
    source={'source':'Имя.md','url':'https://cft.ru','score':.9,'private':'discard'}
    a=normalize_sources([source])[0]
    assert a==normalize_sources([source])[0]
    assert a['doc_id'] and 'private' not in a
    assert normalize_sources([{**source,'doc_id':'given'}])[0]['doc_id']=='given'


def collect(body):
    async def run():
        response=httpx.Response(200,content=body.encode())
        return [value async for value in read_events(response)]
    return asyncio.run(run())


def test_sse_comments_crlf_multiline_unicode_and_eof():
    body=':ping\r\nevent: token\r\ndata: {\r\ndata: "text":"Привет"}\r\n\r\n'+event('done',{})
    assert collect(body)==[('token',{'text':'Привет'}),('done',{})]
    assert collect('event: done\ndata: {}')==[]

@pytest.mark.parametrize('body',['event: token\ndata: {invalid}\n\n','data: '+('x'*1000001)+'\n\n'])
def test_sse_malformed_and_oversized(body):
    with pytest.raises(RagProtocolError): collect(body)
