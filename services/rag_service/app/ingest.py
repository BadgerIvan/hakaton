from io import BytesIO
from pathlib import Path
from uuid import uuid4

import docx
import fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.vectorstore import delete_by_doc_id, get_vectorstore

splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _extract_documents(file_bytes: bytes, filename: str, doc_id: str) -> list[Document]:
    ext = Path(filename).suffix.lower()
    raw_docs: list[Document] = []

    if ext == ".pdf":
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
            for page_num, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    raw_docs.append(
                        Document(
                            page_content=text,
                            metadata={"doc_id": doc_id, "source": filename, "page": page_num},
                        )
                    )
    elif ext == ".docx":
        document = docx.Document(BytesIO(file_bytes))
        blocks = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
        text = "\n".join(blocks)
        if text:
            raw_docs.append(
                Document(
                    page_content=text,
                    metadata={"doc_id": doc_id, "source": filename, "page": None},
                )
            )
    elif ext in {".txt", ".md"}:
        text = file_bytes.decode("utf-8", errors="ignore").strip()
        if text:
            raw_docs.append(
                Document(
                    page_content=text,
                    metadata={"doc_id": doc_id, "source": filename, "page": None},
                )
            )
    else:
        raise ValueError(f"Формат '{ext}' не поддерживается. Допустимы: .pdf, .docx, .txt, .md")

    return raw_docs


def index_file(file_bytes: bytes, filename: str, doc_id: str | None = None) -> tuple[str, int]:
    doc_id = doc_id or str(uuid4())
    raw_docs = _extract_documents(file_bytes, filename, doc_id)
    if not raw_docs:
        raise ValueError(
            "Не удалось извлечь текст из файла (возможно, файл пуст или это PDF-скан без текстового слоя)."
        )

    chunks = splitter.split_documents(raw_docs)

    # При повторной загрузке с тем же doc_id старые чанки удаляются
    delete_by_doc_id(doc_id)

    store = get_vectorstore()
    store.add_documents(chunks)
    return doc_id, len(chunks)