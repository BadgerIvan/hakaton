import os
from uuid import uuid4
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import SparseEmbeddings, SparseVector
from qdrant_client import QdrantClient
from app import vectorstore

pytestmark=pytest.mark.integration

class Dense(Embeddings):
    def embed_documents(self,texts):return [self.embed_query(t) for t in texts]
    def embed_query(self,text):return [1.,0.,0.] if 'Go' in text else [0.,1.,0.]

class Sparse(SparseEmbeddings):
    def embed_documents(self,texts):return [self.embed_query(t) for t in texts]
    def embed_query(self,text):return SparseVector(indices=[1 if 'Go' in text else 2],values=[1.])

@pytest.fixture
def store(monkeypatch):
    url=os.getenv('TEST_QDRANT_URL')
    if not url:pytest.skip('Set TEST_QDRANT_URL to a dedicated Qdrant instance')
    client=QdrantClient(url=url)
    name='test_'+uuid4().hex
    monkeypatch.setattr(vectorstore,'qdrant_client',client)
    monkeypatch.setattr(vectorstore.settings,'qdrant_collection',name)
    monkeypatch.setattr(vectorstore.settings,'embed_dim',3)
    monkeypatch.setattr(vectorstore,'embedder',Dense())
    monkeypatch.setattr(vectorstore,'get_sparse_embedder',lambda:Sparse())
    vectorstore.ensure_collection(retries=1,delay=0)
    yield vectorstore.get_vectorstore()
    client.delete_collection(name);client.close()


def test_hybrid_search_inventory_and_filtered_delete(store):
    store.add_documents([Document(page_content='Go course',metadata={'source':'school/go.md','category':'school'}),
                         Document(page_content='Python course',metadata={'source':'school/python.md','category':'school'})])
    result=store.similarity_search_with_score('Go',k=1)
    assert result[0][0].metadata['source']=='school/go.md'
    assert {d.source for d in vectorstore.list_documents()}=={'school/go.md','school/python.md'}
    vectorstore.delete_document_points('school/go.md')
    assert [d.source for d in vectorstore.list_documents()]==['school/python.md']


def test_recreate_collection_removes_old_points(store):
    store.add_documents([Document(page_content='Go course',metadata={'source':'old.md'})])
    vectorstore.recreate_collection()
    assert vectorstore.list_documents()==[]
