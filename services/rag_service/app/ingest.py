from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.config import settings
from app.schemas import DocumentInfo, ReindexResponse
from app.vectorstore import get_vectorstore, recreate_collection

BATCH_SIZE = 64
ALLOWED_EXTENSIONS = {".txt", ".md"}

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    separators=["\n\n", "\n", ". ", " ", ""],
)

md_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ],
    strip_headers=False,
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


def _split_file(
    text: str,
    ext: str,
    category: str,
    rel_source: str,
    filename: str,
    doc_title: str,
) -> list[Document]:
    base_prefix = f"Раздел: {category.replace('/', ' / ')} | Документ: {doc_title}"
    chunks: list[Document] = []

    if ext == ".md":
        sections = md_header_splitter.split_text(text)
        for section in sections:
            section_text = section.page_content.strip()
            if not section_text:
                continue

            headers = [
                section.metadata[key]
                for key in ("h1", "h2", "h3")
                if key in section.metadata
            ]
            headers_str = " / ".join(headers)
            chunk_header = (
                f"[{base_prefix} | {headers_str}]\n"
                if headers_str
                else f"[{base_prefix}]\n"
            )

            for chunk_text in text_splitter.split_text(section_text):
                chunks.append(
                    Document(
                        page_content=f"{chunk_header}{chunk_text}",
                        metadata={
                            "category": category,
                            "source": rel_source,
                            "filename": filename,
                            "headers": headers_str,
                        },
                    )
                )
    else:
        chunk_header = f"[{base_prefix}]\n"
        for chunk_text in text_splitter.split_text(text):
            chunks.append(
                Document(
                    page_content=f"{chunk_header}{chunk_text}",
                    metadata={
                        "category": category,
                        "source": rel_source,
                        "filename": filename,
                        "headers": "",
                    },
                )
            )

    return chunks


def index_dataset(data_dir: str | None = None) -> ReindexResponse:
    root = Path(data_dir or settings.data_dir)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Папка датасета не найдена: {root}")

    dataset_files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in ALLOWED_EXTENSIONS
        and not _is_hidden(path.relative_to(root))
    )
    if not dataset_files:
        raise ValueError(f"В папке {root} и её подпапках нет ни одного .txt или .md файла")

    all_chunks: list[Document] = []
    file_stats: list[DocumentInfo] = []
    folders_seen: set[str] = set()

    for path in dataset_files:
        text = _read_text_file(path)
        if not text:
            continue

        rel_path = path.relative_to(root)
        rel_source = rel_path.as_posix()
        category = rel_path.parent.as_posix() if rel_path.parent != Path(".") else "общее"
        doc_title = path.stem.replace("_", " ").replace("-", " ")

        file_chunks = _split_file(
            text=text,
            ext=path.suffix.lower(),
            category=category,
            rel_source=rel_source,
            filename=path.name,
            doc_title=doc_title,
        )
        if not file_chunks:
            continue

        folders_seen.add(category)
        all_chunks.extend(file_chunks)
        file_stats.append(
            DocumentInfo(
                category=category,
                source=rel_source,
                chunks=len(file_chunks),
            )
        )

    if not all_chunks:
        raise ValueError("Все найденные .txt и .md файлы оказались пустыми")

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