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


def _is_hidden(rel_path: Path) -> bool:
    return any(part.startswith(".") for part in rel_path.parts)


def index_dataset(data_dir: str | None = None) -> ReindexResponse:
    root = Path(data_dir or settings.data_dir)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Папка датасета не найдена: {root}")

    txt_files = sorted(
        path
        for path in root.rglob("*.txt")
        if path.is_file() and not _is_hidden(path.relative_to(root))
    )
    if not txt_files:
        raise ValueError(f"В папке {root} и её подпапках нет ни одного .txt файла")

    all_chunks: list[Document] = []
    file_stats: list[DocumentInfo] = []
    folders_seen: set[str] = set()

    for path in txt_files:
        text = _read_text_file(path)
        if not text:
            continue

        rel_path = path.relative_to(root)
        rel_source = rel_path.as_posix()
        category = rel_path.parent.as_posix() if rel_path.parent != Path(".") else "общее"
        folders_seen.add(category)

        doc_title = path.stem.replace("_", " ").replace("-", " ")
        chunk_header = f"[Раздел: {category.replace('/', ' / ')} | Документ: {doc_title}]\n"

        raw_chunks = splitter.split_text(text)
        for chunk_text in raw_chunks:
            all_chunks.append(
                Document(
                    page_content=f"{chunk_header}{chunk_text}",
                    metadata={
                        "category": category,
                        "source": rel_source,
                        "filename": path.name,
                    },
                )
            )

        file_stats.append(
            DocumentInfo(
                category=category,
                source=rel_source,
                chunks=len(raw_chunks),
            )
        )

    if not all_chunks:
        raise ValueError("Все найденные .txt файлы оказались пустыми")

    recreate_collection()
    store = get_vectorstore()

    for i in range(0, len(all_chunks), BATCH_SIZE):
        store.add_documents(all_chunks[i : i + BATCH_SIZE])

    return ReindexResponse(
        folders_found=len(folders_seen),
        files_indexed=len(file_stats),
        total_chunks=len(all_chunks),
        files=file_stats,
    )