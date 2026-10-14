import uuid
from datetime import datetime, timedelta, timezone
import jwt

import pytest

from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from app.routers.web.websocket import websocket_endpoint
from app.security import create_access_token
from app.services.auth import SECRET_KEY, ALGORITHM
from app.services.websocket import manager

from db.models.messages import Conversation, ConversationMember, Message
from db.models.users import User

from conftest import FakeWebSocket



def test_websocket_accepts_authenticated_user(user):
    token = create_access_token(user.id)

    client = TestClient(app)
    client.cookies.set("access_token", token)

    with client.websocket_connect(
        f"/ws/{user.id}",
    ) as websocket:
        assert websocket is not None


def test_websocket_closes_for_wrong_user(user):
    token = create_access_token(user.id)

    client = TestClient(app)
    client.cookies.set("access_token", token)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/ws/999"
        ):
            pass

    assert exc_info.value.code == 1008


def test_websocket_closes_for_invalid_token(user):
    client = TestClient(app)
    client.cookies.set("access_token", "invalid-token")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws/{user.id}",
        ):
            pass

    assert exc_info.value.code == 1008

def test_websocket_closes_for_expired_token(user):
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    token = jwt.encode(
        {
            "sub": str(user.id),
            "exp": expired_at,
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    client = TestClient(app)
    client.cookies.set("access_token", token)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws/{user.id}",
        ):
            pass

    assert exc_info.value.code == 1008


def test_websocket_receives_online_users(user):
    token = create_access_token(user.id)

    client = TestClient(app)
    client.cookies.set("access_token", token)

    with client.websocket_connect(
        f"/ws/{user.id}",
    ) as websocket:
        data = websocket.receive_json()

        assert data == {
            "type": "online_users",
            "user_ids": [user.id],
        }


def test_first_websocket_connection_broadcasts_online_status(user):
    token = create_access_token(user.id)

    client = TestClient(app)
    client.cookies.set("access_token", token)

    with client.websocket_connect(
        f"/ws/{user.id}",
    ) as websocket:
        online_users = websocket.receive_json()

        assert online_users == {
            "type": "online_users",
            "user_ids": [user.id],
        }

        status = websocket.receive_json()

        assert status == {
            "type": "user_status",
            "user_id": user.id,
            "status": "online",
        }


def test_second_websocket_connection_does_not_broadcast_online_status(user):
    token = create_access_token(user.id)

    client = TestClient(app)
    client.cookies.set("access_token", token)

    with client.websocket_connect(
        f"/ws/{user.id}"
    ) as first_websocket:

        online_users = first_websocket.receive_json()

        assert online_users == {
            "type": "online_users",
            "user_ids": [user.id],
        }

        status = first_websocket.receive_json()

        assert status == {
            "type": "user_status",
            "user_id": user.id,
            "status": "online",
        }

        with client.websocket_connect(
            f"/ws/{user.id}",
        ) as second_websocket:

            second_online_users = second_websocket.receive_json()

            assert second_online_users == {
                "type": "online_users",
                "user_ids": [user.id],
            }


# тесты для send_message
@pytest.mark.asyncio
async def test_websocket_send_message(
    user,
    second_user,
    session,
    monkeypatch,
):

    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    websocket = FakeWebSocket([
        {
            "type": "send_message",
            "conversation_id": str(conversation.id),
            "text": "Привет!"
        }
    ])

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        new_messages = [
            data
            for data in websocket.sent_messages
            if data["type"] == "new_message"
        ]

        assert len(new_messages) == 1

        message_data = new_messages[0]["message"]

        assert message_data["conversation_id"] == str(conversation.id)
        assert message_data["sender_id"] == user.id
        assert message_data["text"] == "Привет!"

        saved_message = await session.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id
            )
        )

        assert saved_message is not None
        assert saved_message.sender_id == user.id
        assert saved_message.text == "Привет!"

    finally:
        manager.active_connections.clear()



@pytest.mark.asyncio
async def test_websocket_send_message_to_other_user(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    sender_websocket = FakeWebSocket([
        {
            "type": "send_message",
            "conversation_id": str(conversation.id),
            "text": "Привет!",
        }
    ])

    recipient_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(user.id, sender_websocket)
        await manager.connect(second_user.id, recipient_websocket)

        await websocket_endpoint(
            websocket=sender_websocket,
            user_id=user.id,
            session=session,
        )

        recipient_messages = [
            data
            for data in recipient_websocket.sent_messages
            if data["type"] == "new_message"
        ]

        assert len(recipient_messages) == 1

        message_data = recipient_messages[0]["message"]

        assert message_data["conversation_id"] == str(conversation.id)
        assert message_data["sender_id"] == user.id
        assert message_data["text"] == "Привет!"

    finally:
        manager.active_connections.clear()



@pytest.mark.asyncio
async def test_websocket_send_message_to_foreign_conversation(
    user,
    second_user,
    session,
    monkeypatch,
):

    third_user = User(
        username="third_user",
        email="third@example.com",
        password_hash="test_hash",
    )
    session.add(third_user)
    await session.flush()

    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=third_user.id,
        ),
    ])
    await session.flush()

    websocket = FakeWebSocket([
        {
            "type": "send_message",
            "conversation_id": str(conversation.id),
            "text": "Чужое сообщение",
        }
    ])

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        errors = [
            data
            for data in websocket.sent_messages
            if data["type"] == "error"
        ]

        assert len(errors) == 1

        saved_message = await session.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id
            )
        )

        assert saved_message is None

    finally:
        manager.active_connections.clear()



@pytest.mark.parametrize("text", ["", "   "])
@pytest.mark.asyncio
async def test_websocket_does_not_send_empty_message(
    text,
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    websocket = FakeWebSocket([
        {
            "type": "send_message",
            "conversation_id": str(conversation.id),
            "text": text,
        }
    ])

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        new_messages = [
            data
            for data in websocket.sent_messages
            if data["type"] == "new_message"
        ]

        assert new_messages == []

        saved_message = await session.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id
            )
        )

        assert saved_message is None

    finally:
        manager.active_connections.clear()



@pytest.mark.asyncio
async def test_websocket_ignores_invalid_conversation_id(
    user,
    session,
    monkeypatch,
):
    websocket = FakeWebSocket([
        {
            "type": "send_message",
            "conversation_id": "not-a-uuid",
            "text": "Привет!",
        }
    ])

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        new_messages = [
            data
            for data in websocket.sent_messages
            if data["type"] == "new_message"
        ]
        assert new_messages == []

        errors = [
            data
            for data in websocket.sent_messages
            if data["type"] == "error"
        ]
        assert errors == []

        saved_message = await session.scalar(
            select(Message)
        )
        assert saved_message is None

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_send_message_to_nonexistent_conversation(
    user,
    session,
    monkeypatch,
):
    nonexistent_conversation_id = uuid.uuid4()

    websocket = FakeWebSocket([
        {
            "type": "send_message",
            "conversation_id": str(nonexistent_conversation_id),
            "text": "Привет!",
        }
    ])

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        errors = [
            data
            for data in websocket.sent_messages
            if data["type"] == "error"
        ]

        assert len(errors) == 1

        saved_message = await session.scalar(
            select(Message).where(
                Message.conversation_id
                == nonexistent_conversation_id
            )
        )

        assert saved_message is None

        new_messages = [
            data
            for data in websocket.sent_messages
            if data["type"] == "new_message"
        ]

        assert new_messages == []

    finally:
        manager.active_connections.clear()


# тесты для typing
@pytest.mark.parametrize("is_typing", [True, False])
@pytest.mark.asyncio
async def test_websocket_typing_sends_event_to_other_user(
    user,
    second_user,
    session,
    monkeypatch,
    is_typing
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    sender_websocket = FakeWebSocket([
        {
            "type": "typing",
            "conversation_id": str(conversation.id),
            "is_typing": is_typing
        }
    ])

    recipient_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(user.id, sender_websocket)
        await manager.connect(second_user.id, recipient_websocket)

        await websocket_endpoint(
            websocket=sender_websocket,
            user_id=user.id,
            session=session,
        )

        typing_events = [
            data
            for data in recipient_websocket.sent_messages
            if data["type"] == "typing"
        ]

        assert typing_events == [
            {
                "type": "typing",
                "conversation_id": str(conversation.id),
                "user_id": user.id,
                "is_typing": is_typing,
            }
        ]

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_typing_ignores_non_member(
    user,
    second_user,
    session,
    monkeypatch,
):
    third_user = User(
        username="third_user",
        email="third@example.com",
        password_hash="test_hash",
    )
    session.add(third_user)
    await session.flush()

    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=third_user.id,
        ),
    ])
    await session.flush()

    sender_websocket = FakeWebSocket([
        {
            "type": "typing",
            "conversation_id": str(conversation.id),
            "is_typing": True,
        }
    ])
    recipient_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(
            second_user.id,
            recipient_websocket,
        )

        await websocket_endpoint(
            websocket=sender_websocket,
            user_id=user.id,
            session=session,
        )

        typing_events = [
            data
            for data in recipient_websocket.sent_messages
            if data["type"] == "typing"
        ]

        assert typing_events == []

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_typing_ignores_invalid_conversation_id(
    user,
    second_user,
    session,
    monkeypatch,
):
    sender_websocket = FakeWebSocket([
        {
            "type": "typing",
            "conversation_id": "not-a-uuid",
            "is_typing": True,
        }
    ])
    recipient_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(
            second_user.id,
            recipient_websocket,
        )

        await websocket_endpoint(
            websocket=sender_websocket,
            user_id=user.id,
            session=session,
        )

        typing_events = [
            data
            for data in recipient_websocket.sent_messages
            if data["type"] == "typing"
        ]

        assert typing_events == []

    finally:
        manager.active_connections.clear()


# тесты для message_read
@pytest.mark.asyncio
async def test_websocket_message_read(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        text="Привет!",
    )
    session.add(message)
    await session.flush()

    message_id = message.id
    conversation_id = conversation.id

    reader_websocket = FakeWebSocket([
        {
            "type": "message_read",
            "message_id": message_id,
            "conversation_id": str(conversation_id),
        }
    ])

    sender_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return second_user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(user.id, sender_websocket)

        await websocket_endpoint(
            websocket=reader_websocket,
            user_id=second_user.id,
            session=session,
        )

        await session.refresh(message)

        assert message.read_at is not None

        read_events = [
            data
            for data in sender_websocket.sent_messages
            if data["type"] == "message_read"
        ]

        assert read_events == [
            {
                "type": "message_read",
                "conversation_id": str(conversation_id),
                "message_id": message_id,
                "user_id": second_user.id,
            }
        ]

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_message_read_updates_unread_count(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    message_to_read = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        text="Первое сообщение",
    )
    unread_message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        text="Второе сообщение",
    )
    session.add_all([message_to_read, unread_message])
    await session.flush()

    message_id = message_to_read.id
    conversation_id = conversation.id

    reader_websocket = FakeWebSocket([
        {
            "type": "message_read",
            "message_id": message_id,
            "conversation_id": str(conversation_id),
        }
    ])

    async def fake_get_websocket_user_id(websocket):
        return second_user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=reader_websocket,
            user_id=second_user.id,
            session=session,
        )

        unread_count_events = [
            data
            for data in reader_websocket.sent_messages
            if data["type"] == "unread_count"
        ]

        assert unread_count_events == [
            {
                "type": "unread_count",
                "count": 1,
            }
        ]

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_cannot_mark_own_message_as_read(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        text="Моё сообщение",
    )
    session.add(message)
    await session.flush()

    message_id = message.id
    conversation_id = conversation.id

    websocket = FakeWebSocket([
        {
            "type": "message_read",
            "message_id": message_id,
            "conversation_id": str(conversation_id),
        }
    ])

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        await session.refresh(message)

        assert message.read_at is None

        read_events = [
            data
            for data in websocket.sent_messages
            if data["type"] == "message_read"
        ]

        assert read_events == []

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_does_not_process_already_read_message(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    original_read_at = datetime.now(timezone.utc)

    message = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        text="Уже прочитанное сообщение",
        read_at=original_read_at,
    )
    session.add(message)
    await session.flush()

    message_id = message.id
    conversation_id = conversation.id

    reader_websocket = FakeWebSocket([
        {
            "type": "message_read",
            "message_id": message_id,
            "conversation_id": str(conversation_id),
        }
    ])
    sender_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return second_user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(user.id, sender_websocket)

        await websocket_endpoint(
            websocket=reader_websocket,
            user_id=second_user.id,
            session=session,
        )

        await session.refresh(message)

        assert message.read_at == original_read_at

        read_events = [
            data
            for data in sender_websocket.sent_messages
            if data["type"] == "message_read"
        ]
        assert read_events == []

        unread_count_events = [
            data
            for data in reader_websocket.sent_messages
            if data["type"] == "unread_count"
        ]
        assert unread_count_events == []

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_message_read_ignores_nonexistent_message(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    missing_message_id = 999

    reader_websocket = FakeWebSocket([
        {
            "type": "message_read",
            "message_id": missing_message_id,
            "conversation_id": str(conversation.id),
        }
    ])

    sender_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return second_user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(user.id, sender_websocket)

        await websocket_endpoint(
            websocket=reader_websocket,
            user_id=second_user.id,
            session=session,
        )

        read_events = [
            data
            for data in sender_websocket.sent_messages
            if data["type"] == "message_read"
        ]
        assert read_events == []

        unread_count_events = [
            data
            for data in reader_websocket.sent_messages
            if data["type"] == "unread_count"
        ]
        assert unread_count_events == []

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_message_read_ignores_message_from_another_conversation(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation1 = Conversation()
    session.add(conversation1)
    await session.flush()

    conversation2 = Conversation()
    session.add(conversation2)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation1.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation1.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    message = Message(
        conversation_id=conversation1.id,
        sender_id=user.id,
        text="Сообщение из первого диалога",
    )
    session.add(message)
    await session.flush()

    third_user = User(
        username="third_user",
        email="third_user@example.com",
        password_hash="password_hash",
    )
    session.add(third_user)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation2.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=conversation2.id,
            user_id=third_user.id,
        ),
    ])
    await session.flush()

    reader_websocket = FakeWebSocket([
        {
            "type": "message_read",
            "message_id": message.id,
            "conversation_id": str(conversation2.id),
        }
    ])

    sender_websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return second_user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await manager.connect(user.id, sender_websocket)

        await websocket_endpoint(
            websocket=reader_websocket,
            user_id=second_user.id,
            session=session,
        )

        await session.refresh(message)

        assert message.read_at is None

        read_events = [
            data
            for data in sender_websocket.sent_messages
            if data["type"] == "message_read"
        ]
        assert read_events == []

        unread_count_events = [
            data
            for data in reader_websocket.sent_messages
            if data["type"] == "unread_count"
        ]
        assert unread_count_events == []

    finally:
        manager.active_connections.clear()


# тест для get_unread_count
@pytest.mark.asyncio
async def test_websocket_get_unread_count(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    session.add_all([
        Message(
            conversation_id=conversation.id,
            sender_id=user.id,
            text="Первое сообщение",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=user.id,
            text="Второе сообщение",
        ),
    ])
    await session.flush()

    websocket = FakeWebSocket([
        {"type": "get_unread_count"}
    ])

    async def fake_get_websocket_user_id(websocket):
        return second_user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=second_user.id,
            session=session,
        )

        unread_count_events = [
            data
            for data in websocket.sent_messages
            if data["type"] == "unread_count"
        ]

        assert unread_count_events == [
            {"type": "unread_count", "count": 2}
        ]

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_get_unread_count_returns_zero(
    user,
    second_user,
    session,
    monkeypatch,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        ),
    ])
    await session.flush()

    websocket = FakeWebSocket([
        {"type": "get_unread_count"}
    ])

    async def fake_get_websocket_user_id(websocket):
        return second_user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        await websocket_endpoint(
            websocket=websocket,
            user_id=second_user.id,
            session=session,
        )

        unread_count_events = [
            data
            for data in websocket.sent_messages
            if data["type"] == "unread_count"
        ]

        assert unread_count_events == [
            {"type": "unread_count", "count": 0}
        ]

    finally:
        manager.active_connections.clear()


# тесты для is_offline
@pytest.mark.asyncio
async def test_websocket_disconnect_broadcasts_offline_status(
    user,
    second_user,
    session,
    monkeypatch,
):
    websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        recipient_websocket = FakeWebSocket()
        await manager.connect(
            user_id=second_user.id,
            websocket=recipient_websocket,
        )

        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        status_events = [
            data for data in recipient_websocket.sent_messages
            if data.get("type") == "user_status"
        ]
        
        assert status_events == [
            { "type": "user_status",
                "user_id": user.id,
                "status": "online"
            },
            { 
                "type": "user_status",
                "user_id": user.id,
                "status": "offline"
            } 
        ]

        assert manager.is_online(user.id) is False

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_disconnect_does_not_broadcast_offline_if_connection_remains(
    user,
    second_user,
    session,
    monkeypatch,
):
    websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        remaining_websocket = FakeWebSocket()
        await manager.connect(
            user_id=user.id,
            websocket=remaining_websocket,
        )

        recipient_websocket = FakeWebSocket()
        await manager.connect(
            user_id=second_user.id,
            websocket=recipient_websocket,
        )

        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        assert manager.is_online(user.id) is True
        assert remaining_websocket in manager.active_connections[user.id]

        offline_events = [
            data
            for data in recipient_websocket.sent_messages
            if (
                data.get("type") == "user_status"
                and data.get("user_id") == user.id
                and data.get("status") == "offline"
            )
        ]

        assert offline_events == []

    finally:
        manager.active_connections.clear()


@pytest.mark.asyncio
async def test_websocket_disconnect_does_not_send_offline_to_other_users(
    user,
    second_user,
    session,
    monkeypatch,
):
    websocket = FakeWebSocket()

    async def fake_get_websocket_user_id(websocket):
        return user.id

    monkeypatch.setattr(
        "app.routers.web.websocket.get_websocket_user_id",
        fake_get_websocket_user_id,
    )

    manager.active_connections.clear()

    try:
        remaining_websocket = FakeWebSocket()
        await manager.connect(
            user_id=user.id,
            websocket=remaining_websocket,
        )

        recipient_1 = FakeWebSocket()
        recipient_2 = FakeWebSocket()

        await manager.connect(
            user_id=second_user.id,
            websocket=recipient_1,
        )
        await manager.connect(
            user_id=second_user.id + 1000,
            websocket=recipient_2,
        )

        await websocket_endpoint(
            websocket=websocket,
            user_id=user.id,
            session=session,
        )

        for recipient in (recipient_1, recipient_2):
            offline_events = [
                data
                for data in recipient.sent_messages
                if (
                    data.get("type") == "user_status"
                    and data.get("user_id") == user.id
                    and data.get("status") == "offline"
                )
            ]

            assert offline_events == []

        assert manager.is_online(user.id) is True
        assert remaining_websocket in manager.active_connections[user.id]

    finally:
        manager.active_connections.clear()
