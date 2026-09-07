from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserCreate(BaseModel):
    username: str = Field(
        min_lenght=3,
        max_lenght=50,
        pattern=r"^[a-z0-9_]+$"
    )
    name: str | None = Field(
        default=None,
        max_length=50
    )
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=100
    )


class UserResponse(BaseModel):
    id: int
    username: str
    name: str | None
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


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