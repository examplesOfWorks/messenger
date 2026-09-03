from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )
    name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )
    photo: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )