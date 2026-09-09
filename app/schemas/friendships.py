from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FriendRequestUserResponse(BaseModel):
    id: int
    username: str
    name: str | None
    email: str
    photo: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FriendRequestResponse(BaseModel):
    id: int
    requester_id: int
    addressee_id: int
    status: str
    created_at: datetime
    accepted_at: datetime | None
    requester: FriendRequestUserResponse

    model_config = ConfigDict(from_attributes=True)


class FriendResponse(BaseModel):
    accepted_at: datetime | None
    friend: FriendRequestUserResponse

    model_config = ConfigDict(from_attributes=True)