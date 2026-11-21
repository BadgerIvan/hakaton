from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class SourceChunk(BaseModel):
    source: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class DocumentInfo(BaseModel):
    source: str
    chunks: int


class ReindexResponse(BaseModel):
    files_indexed: int
    total_chunks: int
    files: list[DocumentInfo]