"""Test-only entry point: real RAG/Qdrant/Ollama clients, deterministic sparse vectors."""
from langchain_qdrant import SparseEmbeddings, SparseVector
from app import vectorstore

class OfflineSparse(SparseEmbeddings):
    def embed_documents(self,texts):return [self.embed_query(text) for text in texts]
    def embed_query(self,text):
        return SparseVector(indices=[1 if 'go' in text.lower() else 2],values=[1.])

vectorstore.get_sparse_embedder=lambda:OfflineSparse()
from app.main import app
