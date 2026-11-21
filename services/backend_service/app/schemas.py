from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateConversation(BaseModel):
    title: str = Field(default='Новый диалог', min_length=1, max_length=120)

    @field_validator('title')
    @classmethod
    def trim_title(cls, value):
        if not value.strip():
            raise ValueError('Название не может быть пустым')
        return value.strip()


class AskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    conversation_id: UUID
    request_id: UUID = Field(default_factory=uuid4)
    question: str = Field(min_length=1, max_length=4000)

    @field_validator('question')
    @classmethod
    def trim_question(cls, value):
        if not value.strip():
            raise ValueError('Вопрос не может быть пустым')
        return value.strip()
