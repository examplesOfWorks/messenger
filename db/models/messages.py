from datetime import datetime

import uuid

from sqlalchemy import DateTime, ForeignKey, UUID, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan"
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan"
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="members",
    )

    user: Mapped["User"] = relationship(
        back_populates="conversation_members"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False
    )

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    sender: Mapped["User"] = relationship(
        back_populates="sent_messages"
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages"
    )
