import time
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    Modifier,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from app.config import settings
from app.schemas import DocumentInfo

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

qdrant_client = QdrantClient(url=settings.qdrant_url)

embedder = OllamaEmbeddings(
    model=settings.embed_model,
    base_url=settings.ollama_url,
)

sparse_embedder = FastEmbedSparse(
    model_name=settings.sparse_model,
    language=settings.bm25_language,
)


def _collection_params() -> dict:
    return {
        "vectors_config": {
            DENSE_VECTOR_NAME: VectorParams(
                size=settings.embed_dim,
                distance=Distance.COSINE,
            )
        },
        "sparse_vectors_config": {
            SPARSE_VECTOR_NAME: SparseVectorParams(
                index=SparseIndexParams(on_disk=False),
                modifier=Modifier.IDF,
            )
        },
    }


def ensure_collection(retries: int = 15, delay: float = 2.0) -> None:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            if not qdrant_client.collection_exists(settings.qdrant_collection):
                qdrant_client.create_collection(
                    collection_name=settings.qdrant_collection,
                    **_collection_params(),
                )
            return
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"Qdrant не ответил за {retries * delay:.0f}с: {last_error}")


def recreate_collection() -> None:
    if qdrant_client.collection_exists(settings.qdrant_collection):
        qdrant_client.delete_collection(settings.qdrant_collection)
    qdrant_client.create_collection(
        collection_name=settings.qdrant_collection,
        **_collection_params(),
    )


def get_vectorstore() -> QdrantVectorStore:
    ensure_collection(retries=3, delay=1.0)
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=settings.qdrant_collection,
        embedding=embedder,
        sparse_embedding=sparse_embedder,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name=DENSE_VECTOR_NAME,
        sparse_vector_name=SPARSE_VECTOR_NAME,
    )


def list_documents() -> list[DocumentInfo]:
    ensure_collection(retries=3, delay=1.0)
    counts: dict[tuple[str, str], int] = {}
    offset = None

    while True:
        points, offset = qdrant_client.scroll(
            collection_name=settings.qdrant_collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            meta = (point.payload or {}).get("metadata", {})
            category = str(meta.get("category", "общее"))
            source = str(meta.get("source", "unknown"))
            key = (category, source)
            counts[key] = counts.get(key, 0) + 1

        if offset is None:
            break

    return [
        DocumentInfo(category=cat, source=src, chunks=cnt)
        for (cat, src), cnt in sorted(counts.items())
    ]