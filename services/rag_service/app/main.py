import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app.config import settings
from app.ingest import (
    delete_file_and_vectors,
    index_dataset,
    list_storage_files,
    save_and_index_file,
)
from app.rag import generate_answer, stream_answer
from app.schemas import (
    AdminFileInfo,
    AskRequest,
    AskResponse,
    DocumentInfo,
    ReindexResponse,
    UploadResponse,
)
from app.vectorstore import ensure_collection, list_documents, qdrant_client

reindex_lock = asyncio.Lock()
ADMIN_HTML_PATH = Path(__file__).parent / "static" / "admin.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(ensure_collection)
    yield


app = FastAPI(
    title="Company RAG Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Неверный или отсутствует X-Admin-Token")


@app.get("/health")
async def health():
    qdrant_ok = False
    ollama_ok = False
    installed_models: list[str] = []

    try:
        await asyncio.to_thread(qdrant_client.get_collections)
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
            installed_models = [m["name"] for m in resp.json().get("models", [])]
            ollama_ok = True
    except Exception:
        ollama_ok = False

    def _has_model(target: str) -> bool:
        return any(m == target or m.startswith(f"{target}:") for m in installed_models)

    llm_ready = _has_model(settings.llm_model)
    embed_ready = _has_model(settings.embed_model)

    status_ok = qdrant_ok and ollama_ok and llm_ready and embed_ready
    payload = {
        "status": "ok" if status_ok else "degraded",
        "qdrant": qdrant_ok,
        "ollama": ollama_ok,
        "models": {
            settings.llm_model: llm_ready,
            settings.embed_model: embed_ready,
        },
    }
    if not (qdrant_ok and ollama_ok):
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return FileResponse(ADMIN_HTML_PATH)


@app.get(
    "/api/v1/admin/files",
    response_model=list[AdminFileInfo],
    dependencies=[Depends(verify_admin)],
)
async def admin_list_files():
    return await asyncio.to_thread(list_storage_files)


@app.post(
    "/api/v1/admin/files",
    response_model=UploadResponse,
    dependencies=[Depends(verify_admin)],
)
async def admin_upload_files(
    files: list[UploadFile] = File(...),
    category: str = Form(default=""),
):
    if reindex_lock.locked():
        raise HTTPException(status_code=409, detail="Индексация уже выполняется")

    async with reindex_lock:
        uploaded: list[DocumentInfo] = []
        total_chunks = 0
        for upload in files:
            raw = await upload.read()
            try:
                info = await asyncio.to_thread(
                    save_and_index_file,
                    upload.filename or "",
                    raw,
                    category,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Ошибка индексации файла {upload.filename}: {exc}",
                )
            uploaded.append(info)
            total_chunks += info.chunks

        return UploadResponse(uploaded=uploaded, total_chunks_added=total_chunks)


@app.delete("/api/v1/admin/files", dependencies=[Depends(verify_admin)])
async def admin_delete_file(source: str = Query(..., min_length=1)):
    if reindex_lock.locked():
        raise HTTPException(status_code=409, detail="Индексация уже выполняется")

    async with reindex_lock:
        try:
            await asyncio.to_thread(delete_file_and_vectors, source)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Ошибка удаления: {exc}")
        return {"deleted": source}


@app.post(
    "/api/v1/admin/reindex",
    response_model=ReindexResponse,
    dependencies=[Depends(verify_admin)],
)
async def admin_reindex():
    if reindex_lock.locked():
        raise HTTPException(status_code=409, detail="Индексация уже выполняется")

    async with reindex_lock:
        try:
            return await asyncio.to_thread(index_dataset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Ошибка индексации (проверьте модель {settings.embed_model}): {exc}",
            )


@app.get("/api/v1/documents", response_model=list[DocumentInfo])
async def get_documents():
    return await asyncio.to_thread(list_documents)


@app.post("/api/v1/reindex", response_model=ReindexResponse)
async def reindex():
    if reindex_lock.locked():
        raise HTTPException(status_code=409, detail="Индексация уже выполняется")

    async with reindex_lock:
        try:
            return await asyncio.to_thread(index_dataset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Ошибка индексации (проверьте модель {settings.embed_model}): {exc}",
            )


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    try:
        answer, sources = await generate_answer(req.question, req.history)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка генерации ответа: {exc}")
    return AskResponse(answer=answer, sources=sources)


@app.post("/api/v1/ask/stream")
async def ask_stream(req: AskRequest):
    sources, token_stream = await stream_answer(req.question, req.history)

    async def event_generator():
        try:
            async for token in token_stream:
                yield f"event: token\ndata: {json.dumps({'text': token}, ensure_ascii=False)}\n\n"

            yield f"event: sources\ndata: {json.dumps([s.model_dump() for s in sources], ensure_ascii=False)}\n\n"

            yield "event: done\ndata: {}\n\n"
        except Exception as exc:
            logger.exception("Ошибка стриминга: %s", exc)
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")