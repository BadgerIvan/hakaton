import time
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.config import settings
from app.schemas import DocumentInfo

qdrant_client = QdrantClient(url=settings.qdrant_url)

# Эмбеддер принудительно на CPU, чтобы оставить 6 ГБ VRAM целиком под qwen3:4b
embedder = OllamaEmbeddings(
    model=settings.embed_model,
    base_url=settings.ollama_url,
    num_gpu=0,
)


def ensure_collection(retries: int = 15, delay: float = 2.0) -> None:
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


def recreate_collection() -> None:
    if qdrant_client.collection_exists(settings.qdrant_collection):
        qdrant_client.delete_collection(settings.qdrant_collection)
    qdrant_client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(
            size=settings.embed_dim,
            distance=Distance.COSINE,
        ),
    )


def get_vectorstore() -> QdrantVectorStore:
    ensure_collection(retries=3, delay=1.0)
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=settings.qdrant_collection,
        embedding=embedder,
        retrieval_mode=RetrievalMode.DENSE,
    )


def list_documents() -> list[DocumentInfo]:
    ensure_collection(retries=3, delay=1.0)
    counts: dict[str, int] = {}
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
            source = str(meta.get("source", "unknown"))
            counts[source] = counts.get(source, 0) + 1

        if offset is None:
            break

    return [
        DocumentInfo(source=src, chunks=cnt)
        for src, cnt in sorted(counts.items())
    ]