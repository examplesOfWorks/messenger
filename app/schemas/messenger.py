from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class ConversationUserResponse(BaseModel):
    id: int
    username: str
    photo: str | None

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    other_user: ConversationUserResponse