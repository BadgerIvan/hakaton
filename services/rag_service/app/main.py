import asyncio
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.ingest import index_file
from app.rag import generate_answer, stream_answer
from app.schemas import AskRequest, AskResponse, DocumentInfo, UploadResponse
from app.vectorstore import delete_by_doc_id, ensure_collection, list_documents, qdrant_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(ensure_collection)
    yield


app = FastAPI(title="Company RAG Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/v1/documents", response_model=list[DocumentInfo])
async def get_documents():
    return await asyncio.to_thread(list_documents)


@app.post("/api/v1/documents", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Имя файла отсутствует")

    file_bytes = await file.read()
    try:
        saved_id, chunks = await asyncio.to_thread(index_file, file_bytes, file.filename, doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка индексации (проверьте модель {settings.embed_model}): {exc}")

    return UploadResponse(doc_id=saved_id, filename=file.filename, chunks=chunks)


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    await asyncio.to_thread(delete_by_doc_id, doc_id)
    return {"deleted": True, "doc_id": doc_id}


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    try:
        answer, sources = await generate_answer(req.question, req.history)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка генерации ответа: {exc}")
    return AskResponse(answer=answer, sources=sources)


@app.post("/api/v1/ask/stream")
async def ask_stream(req: AskRequest):
    try:
        sources, token_gen = await stream_answer(req.question, req.history)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка поиска контекста: {exc}")

    async def event_stream():
        sources_payload = json.dumps([s.model_dump() for s in sources], ensure_ascii=False)
        yield f"event: sources\ndata: {sources_payload}\n\n"

        try:
            async for token in token_gen:
                payload = json.dumps({"text": token}, ensure_ascii=False)
                yield f"event: token\ndata: {payload}\n\n"
        except Exception as exc:
            err_payload = json.dumps({"detail": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {err_payload}\n\n"
            return

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )