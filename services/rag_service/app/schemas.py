from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class SourceChunk(BaseModel):
    doc_id: str
    source: str
    page: int | None = None
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunks: int


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunks: int