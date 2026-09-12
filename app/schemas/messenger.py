from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, field_validator


class ConversationUserResponse(BaseModel):
    id: int
    username: str
    photo: str | None

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    other_user: ConversationUserResponse


class MessageCreate(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Сообщение не может быть пустым")

        return value


class MessageResponse(BaseModel):
    id: int
    conversation_id: uuid.UUID
    sender_id: int
    text: str
    created_at: datetime
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)