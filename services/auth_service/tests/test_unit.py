import hashlib
import pytest
from pydantic import ValidationError
from app.database import build_engine
from app.main import Registration, Credentials, digest

@pytest.mark.parametrize('url',['sqlite:///users.db','mysql://localhost/db'])
def test_auth_refuses_non_postgres(url):
    with pytest.raises(ValueError): build_engine(url)

@pytest.mark.parametrize('field,value', [('password','        '),('password','short'),('name','  '),('email','not-email')])
def test_bad_registration(field,value):
    account={'name':' Вова ','email':'VOVA@EXAMPLE.COM','password':'correct-pass'}
    account[field]=value
    with pytest.raises(ValidationError): Registration(**account)


def test_registration_normalization_and_token_hash():
    account=Registration(name=' Вова ',email='VOVA@EXAMPLE.COM',password='correct-pass')
    assert account.name=='Вова'
    assert account.email=='vova@example.com'
    assert digest('session')==hashlib.sha256(b'session').hexdigest()
    assert len(digest('session'))==64
