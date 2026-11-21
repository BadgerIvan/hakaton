import time
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    VectorParams,
)

from app.config import settings
from app.schemas import DocumentInfo

qdrant_client = QdrantClient(url=settings.qdrant_url)

embedder = OllamaEmbeddings(
    model=settings.embed_model,
    base_url=settings.ollama_url,
    num_gpu=0,
)


def ensure_collection(retries: int = 15, delay: float = 2.0) -> None:
    """Создаёт коллекцию в Qdrant, дожидаясь старта контейнера при холодном запуске."""
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            if not qdrant_client.collection_exists(settings.qdrant_collection):
                qdrant_client.create_collection(
                    collection_name=settings.qdrant_collection,
                    vectors_config=VectorParams(
                        size=settings.embed_dim,
                        distance=Distance.COSINE,
                    ),
                )
            return
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"Qdrant не ответил за {retries * delay:.0f}с: {last_error}")


def get_vectorstore() -> QdrantVectorStore:
    ensure_collection(retries=3, delay=1.0)
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=settings.qdrant_collection,
        embedding=embedder,
        retrieval_mode=RetrievalMode.DENSE,
    )


def delete_by_doc_id(doc_id: str) -> None:
    ensure_collection(retries=3, delay=1.0)
    qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_id",
                    match=MatchValue(value=doc_id),
                )
            ]
        ),
    )


def list_documents() -> list[DocumentInfo]:
    """Возвращает сводку по всем загруженным документам и количеству их чанков."""
    ensure_collection(retries=3, delay=1.0)
    docs: dict[str, dict[str, str | int]] = {}
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
            doc_id = str(meta.get("doc_id", "unknown"))
            filename = str(meta.get("source", "unknown"))
            if doc_id not in docs:
                docs[doc_id] = {"filename": filename, "chunks": 0}
            docs[doc_id]["chunks"] = int(docs[doc_id]["chunks"]) + 1

        if offset is None:
            break

    return [
        DocumentInfo(
            doc_id=doc_id,
            filename=str(info["filename"]),
            chunks=int(info["chunks"]),
        )
        for doc_id, info in docs.items()
    ]