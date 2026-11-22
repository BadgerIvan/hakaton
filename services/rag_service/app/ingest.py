import re
import logging
from tempfile import NamedTemporaryFile
from pathlib import Path, PurePosixPath

import yaml
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.config import settings
from app.schemas import AdminFileInfo, DocumentInfo, ReindexResponse
from app.vectorstore import (
    delete_document_points,
    get_vectorstore,
    list_documents,
    recreate_collection,
)

from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)
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

_FRONTMATTER_RE = re.compile(
    r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)",
    flags=re.DOTALL,
)

_HEADER_MARKERS = (
    "source_url:",
    "fetch_url:",
    "source_format:",
    "document_id:",
    "parser_version:",
)


def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore").strip()


def _read_text_file(path: Path) -> str:
    return _decode_bytes(path.read_bytes())


def _parse_yaml_block(block: str) -> dict:
    try:
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict):
            return parsed
    except yaml.YAMLError:
        pass

    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith((" ", "\t", "-")):
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        if key and val.lower() not in ("null", "none", "[]", ""):
            result[key] = val
    return result


def _extract_frontmatter(text: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(text)
    if match:
        meta = _parse_yaml_block(match.group(1))
        body = text[match.end() :].strip()
        return meta, body
    
    parts = re.split(r"\r?\n\r?\n", text, maxsplit=1)
    if len(parts) == 2 and any(marker in parts[0] for marker in _HEADER_MARKERS):
        meta = _parse_yaml_block(parts[0])
        if meta:
            return meta, parts[1].strip()

    return {}, text.strip()


_FETCHED_AT_KEYS = (
    "fetched_at",
    "date_parsed",
    "parsed_at",
    "scraped_at",
    "retrieved_at",
    "downloaded_at",
)
_PUBLISHED_AT_KEYS = (
    "published_at",
    "date_published",
    "published",
    "last_modified",
    "updated_at",
    "date",
)
_VERSION_KEYS = (
    "version",
    "doc_version",
    "edition",
    "revision",
    "release",
)
_PAGE_KEYS = (
    "page",
    "page_number",
    "section",
)


def _clean_meta_value(raw: object) -> str | None:
    if isinstance(raw, datetime):
        return raw.isoformat(timespec="seconds")
    if isinstance(raw, date):
        return raw.isoformat()
    return _clean_meta_str(raw)


def _first_meta_str(meta: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        val = _clean_meta_value(meta.get(key))
        if val:
            return val
    return None

def _clean_meta_str(raw: object) -> str | None:
    if raw is None:
        return None
    val = str(raw).strip()
    if not val or val.lower() in ("null", "none"):
        return None
    return val


def _is_hidden(rel_path: Path) -> bool:
    return any(part.startswith(".") for part in rel_path.parts)


def _ensure_root(data_dir: str | None = None) -> Path:
    root = Path(data_dir or settings.data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sanitize_rel_path(category: str, filename: str) -> PurePosixPath:
    clean_name = Path(filename.replace("\\", "/")).name.strip()
    if not clean_name or clean_name.startswith("."):
        raise ValueError(f"Некорректное имя файла: {filename}")

    ext = Path(clean_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Формат {ext or 'без расширения'} не поддерживается (разрешены .txt и .md)")

    raw_cat = category.replace("\\", "/").strip().strip("/")
    parts: list[str] = []
    if raw_cat and raw_cat != "общее":
        for part in raw_cat.split("/"):
            part = part.strip()
            if not part or part in (".", "..") or part.startswith("."):
                raise ValueError(f"Некорректный путь категории: {category}")
            parts.append(part)

    return PurePosixPath(*parts, clean_name)


def _resolve_safe(root: Path, rel_source: str) -> Path:
    rel = PurePosixPath(rel_source.replace("\\", "/").lstrip("/"))
    if not rel.parts or any(p in ("", ".", "..") or p.startswith(".") for p in rel.parts):
        raise ValueError(f"Некорректный путь файла: {rel_source}")
    target = (root / Path(*rel.parts)).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Выход за пределы каталога хранения запрещён")
    return target


def _split_file(
    text: str,
    ext: str,
    category: str,
    rel_source: str,
    filename: str,
    doc_title: str,
    source_url: str | None = None,
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
                            "title": doc_title,
                            "source_url": source_url,
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
                        "title": doc_title,
                        "source_url": source_url,
                        "headers": "",
                    },
                )
            )

    return chunks


def _build_chunks_for_path(
    file_path: Path,
    base_dir: Path,
    source_path: Path | None = None,
) -> tuple[str, str, list[Document]]:
    logical_path = source_path or file_path
    rel_path = logical_path.relative_to(base_dir)
    rel_source = rel_path.as_posix()
    folder_category = (
        rel_path.parent.as_posix() if rel_path.parent != Path(".") else "общее"
    )

    raw_text = _decode_bytes(file_path.read_bytes())
    if not raw_text:
        return folder_category, rel_source, []

    meta, body = _extract_frontmatter(raw_text)
    category = _clean_meta_str(meta.get("category")) or folder_category
    if not body.strip():
        return category, rel_source, []

    doc_title = (
        _clean_meta_str(meta.get("title"))
        or logical_path.stem.replace("_", " ").replace("-", " ").strip()
    )
    source_url = _first_meta_str(meta, ("source_url", "fetch_url", "url"))

    fetched_at = _first_meta_str(meta, _FETCHED_AT_KEYS) or datetime.fromtimestamp(
        file_path.stat().st_mtime, tz=timezone.utc
    ).strftime("%Y-%m-%d")
    published_at = _first_meta_str(meta, _PUBLISHED_AT_KEYS)
    version = _first_meta_str(meta, _VERSION_KEYS)
    page_or_section = _first_meta_str(meta, _PAGE_KEYS)

    chunks = _split_file(
        text=body,
        ext=logical_path.suffix.lower(),
        category=category,
        rel_source=rel_source,
        filename=logical_path.name,
        doc_title=doc_title,
        source_url=source_url,
    )

    for chunk in chunks:
        chunk.metadata["fetched_at"] = fetched_at
        chunk.metadata["published_at"] = published_at
        chunk.metadata["version"] = version
        if page_or_section:
            chunk.metadata["page"] = page_or_section

    return category, rel_source, chunks


def save_and_index_file(
    filename: str,
    raw_bytes: bytes,
    category: str = "",
    data_dir: str | None = None,
) -> DocumentInfo:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise ValueError(f"Файл {filename} превышает лимит {settings.max_upload_mb} МБ")

    text_preview = _decode_bytes(raw_bytes)
    if not text_preview:
        raise ValueError(f"Файл {filename} пуст")

    root = _ensure_root(data_dir)
    rel_posix = _sanitize_rel_path(category, filename)
    target = _resolve_safe(root, rel_posix.as_posix())
    target.parent.mkdir(parents=True, exist_ok=True)
    # Validate a staged file first. A malformed update must not erase the old file.
    staged = None
    try:
        with NamedTemporaryFile(dir=target.parent, prefix=".upload-", suffix=target.suffix, delete=False) as temp:
            staged = Path(temp.name)
            temp.write(raw_bytes)
        resolved_category, rel_source, chunks = _build_chunks_for_path(staged, root, source_path=target)
        if not chunks:
            raise ValueError(f"Не удалось извлечь текст из файла {filename}")

        delete_document_points(rel_source)
        store = get_vectorstore()
        for i in range(0, len(chunks), BATCH_SIZE):
            store.add_documents(chunks[i : i + BATCH_SIZE])
        staged.replace(target)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)

    return DocumentInfo(
        category=resolved_category,
        source=rel_source,
        chunks=len(chunks),
    )


def delete_file_and_vectors(source: str, data_dir: str | None = None) -> None:
    root = _ensure_root(data_dir)
    target = _resolve_safe(root, source)
    rel_source = target.relative_to(root).as_posix()

    delete_document_points(rel_source)

    if target.exists() and target.is_file():
        target.unlink()
        parent = target.parent
        while parent != root:
            try:
                parent.rmdir()
                parent = parent.parent
            except OSError:
                break


def list_storage_files(data_dir: str | None = None) -> list[AdminFileInfo]:
    root = _ensure_root(data_dir)
    indexed_map = {doc.source: doc for doc in list_documents()}

    disk_files: dict[str, tuple[str, int]] = {}
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and path.resolve().is_relative_to(root)
            and path.suffix.lower() in ALLOWED_EXTENSIONS
            and not _is_hidden(path.relative_to(root))
        ):
            rel_path = path.relative_to(root)
            rel_source = rel_path.as_posix()
            category = rel_path.parent.as_posix() if rel_path.parent != Path(".") else "общее"
            disk_files[rel_source] = (category, path.stat().st_size)

    all_sources = sorted(set(disk_files.keys()) | set(indexed_map.keys()))
    result: list[AdminFileInfo] = []

    for src in all_sources:
        on_disk = src in disk_files
        indexed_doc = indexed_map.get(src)
        category = disk_files[src][0] if on_disk else indexed_doc.category
        size_bytes = disk_files[src][1] if on_disk else 0
        chunks = indexed_doc.chunks if indexed_doc else 0
        result.append(
            AdminFileInfo(
                category=category,
                source=src,
                size_bytes=size_bytes,
                chunks=chunks,
                on_disk=on_disk,
                indexed=chunks > 0,
            )
        )

    return result


def index_dataset(data_dir: str | None = None) -> ReindexResponse:
    root = _ensure_root(data_dir)

    dataset_files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.resolve().is_relative_to(root)
        and path.suffix.lower() in ALLOWED_EXTENSIONS
        and not _is_hidden(path.relative_to(root))
    )
    if not dataset_files:
        raise ValueError("В каталоге данных нет .txt и .md файлов; существующий индекс сохранён")

    all_chunks: list[Document] = []
    file_stats: list[DocumentInfo] = []
    folders_seen: set[str] = set()

    for path in dataset_files:
        category, rel_source, file_chunks = _build_chunks_for_path(path, root)
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

    logger.info("index.rebuild_started", extra={"files": len(file_stats), "chunks": len(all_chunks)})
    recreate_collection()
    store = get_vectorstore()

    for i in range(0, len(all_chunks), BATCH_SIZE):
        store.add_documents(all_chunks[i : i + BATCH_SIZE])

    logger.info("index.rebuild_finished", extra={"files": len(file_stats), "chunks": len(all_chunks)})
    return ReindexResponse(
        folders_found=len(folders_seen),
        files_indexed=len(file_stats),
        total_chunks=len(all_chunks),
        files=file_stats,
    )
