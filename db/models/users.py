from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    sent_friend_requests: Mapped[list["Friendship"]] = relationship(
        foreign_keys="Friendship.requester_id",
        back_populates="requester",
    )

    received_friend_requests: Mapped[list["Friendship"]] = relationship(
        foreign_keys="Friendship.addressee_id",
        back_populates="addressee",
    )


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )
    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    addressee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    requester: Mapped["User"] = relationship(
        foreign_keys=[requester_id],
        back_populates="sent_friend_requests",
    )
    addressee: Mapped["User"] = relationship(
        foreign_keys=[addressee_id],
        back_populates="received_friend_requests",
    )
    __table_args__ = (
        Index(
            "uq_friendships_pair",
            func.least(requester_id, addressee_id),
            func.greatest(requester_id, addressee_id),
            unique=True,
        ),
        CheckConstraint(
            "requester_id <> addressee_id",
            name="ck_friendships_different_users",
        ),
    )
