from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


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
