from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.schemas import DocumentInfo, ReindexResponse
from app.vectorstore import get_vectorstore, recreate_collection

BATCH_SIZE = 64

splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore").strip()


def index_dataset(data_dir: str | None = None) -> ReindexResponse:
    root = Path(data_dir or settings.data_dir)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Папка датасета не найдена: {root}")

    txt_files = sorted(root.rglob("*.txt"))
    if not txt_files:
        raise ValueError(f"В папке {root} нет ни одного .txt файла")

    all_chunks: list[Document] = []
    file_stats: list[DocumentInfo] = []

    for path in txt_files:
        text = _read_text_file(path)
        if not text:
            continue

        rel_source = path.relative_to(root).as_posix()
        doc = Document(page_content=text, metadata={"source": rel_source})
        chunks = splitter.split_documents([doc])

        all_chunks.extend(chunks)
        file_stats.append(DocumentInfo(source=rel_source, chunks=len(chunks)))

    if not all_chunks:
        raise ValueError("Все найденные .txt файлы оказались пустыми")

    recreate_collection()
    store = get_vectorstore()

    for i in range(0, len(all_chunks), BATCH_SIZE):
        store.add_documents(all_chunks[i : i + BATCH_SIZE])

    return ReindexResponse(
        files_indexed=len(file_stats),
        total_chunks=len(all_chunks),
        files=file_stats,
    )