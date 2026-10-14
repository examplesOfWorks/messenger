import uuid
import pytest

from db.models.users import User
from app.services.websocket import ConnectionManager, get_other_user_id
from db.models.messages import Conversation, ConversationMember

from conftest import FakeWebSocket, BrokenFakeWebSocket



# тест для connect
@pytest.mark.asyncio
async def test_connect_adds_user_to_active_connections():
    manager = ConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(
        user_id=1,
        websocket=websocket,
    )

    assert websocket.accepted is True
    assert manager.is_online(1) is True
    assert websocket in manager.active_connections[1]


# тесты для disconnect
@pytest.mark.asyncio
async def test_disconnect_removes_last_connection():
    manager = ConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(
        user_id=1,
        websocket=websocket,
    )

    result = manager.disconnect(
        user_id=1,
        websocket=websocket,
    )

    assert result is True
    assert manager.is_online(1) is False
    assert 1 not in manager.active_connections


@pytest.mark.asyncio
async def test_disconnect_does_not_take_user_offline_if_other_connection_exists():
    manager = ConnectionManager()

    websocket_1 = FakeWebSocket()
    websocket_2 = FakeWebSocket()

    await manager.connect(
        user_id=1,
        websocket=websocket_1,
    )

    await manager.connect(
        user_id=1,
        websocket=websocket_2,
    )

    result = manager.disconnect(
        user_id=1,
        websocket=websocket_1,
    )

    assert result is False
    assert manager.is_online(1) is True
    assert websocket_1 not in manager.active_connections[1]
    assert websocket_2 in manager.active_connections[1]


# тест для send_online_users
@pytest.mark.asyncio
async def test_send_online_users():
    manager = ConnectionManager()

    websocket_1 = FakeWebSocket()
    websocket_2 = FakeWebSocket()
    websocket_for_message = FakeWebSocket()

    await manager.connect(
        user_id=1,
        websocket=websocket_1,
    )

    await manager.connect(
        user_id=2,
        websocket=websocket_2,
    )

    await manager.send_online_users(
        websocket_for_message
    )

    assert websocket_for_message.sent_messages == [
        {
            "type": "online_users",
            "user_ids": [1, 2],
        }
    ]


# тест для broadcast
@pytest.mark.asyncio
async def test_broadcast_sends_message_to_all_connections():
    manager = ConnectionManager()

    websocket_1 = FakeWebSocket()
    websocket_2 = FakeWebSocket()

    await manager.connect(
        user_id=1,
        websocket=websocket_1,
    )

    await manager.connect(
        user_id=2,
        websocket=websocket_2,
    )

    data = {
        "type": "test",
        "message": "Привет!",
    }

    await manager.broadcast(data)

    assert websocket_1.sent_messages == [data]
    assert websocket_2.sent_messages == [data]


@pytest.mark.asyncio
async def test_broadcast_removes_broken_connection_and_sends_to_others():
    manager = ConnectionManager()

    broken_websocket = BrokenFakeWebSocket()
    working_websocket = FakeWebSocket()

    await manager.connect(
        user_id=1,
        websocket=broken_websocket,
    )
    await manager.connect(
        user_id=2,
        websocket=working_websocket,
    )

    data = {
        "type": "test",
        "message": "Привет!",
    }

    await manager.broadcast(data)

    assert 1 not in manager.active_connections
    assert working_websocket.sent_messages == [data]


# тесты для send_to_user
@pytest.mark.asyncio
async def test_send_to_user_removes_broken_connection():
    manager = ConnectionManager()

    broken_websocket = BrokenFakeWebSocket()
    working_websocket = FakeWebSocket()

    await manager.connect(
        user_id=1,
        websocket=broken_websocket,
    )

    await manager.connect(
        user_id=1,
        websocket=working_websocket,
    )

    data = {
        "type": "test",
        "message": "Привет!",
    }

    await manager.send_to_user(
        user_id=1,
        data=data,
    )

    assert broken_websocket not in manager.active_connections[1]
    assert working_websocket in manager.active_connections[1]
    assert working_websocket.sent_messages == [data]


@pytest.mark.asyncio
async def test_send_to_user_does_nothing_if_user_is_offline():
    manager = ConnectionManager()

    data = {
        "type": "test",
        "message": "Привет!",
    }

    await manager.send_to_user(
        user_id=1,
        data=data,
    )

    assert 1 not in manager.active_connections


# тесты для get_other_user_id
@pytest.mark.asyncio
async def test_get_other_user_id(
    session,
    user,
    second_user,
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all(
        [
            ConversationMember(
                conversation_id=conversation.id,
                user_id=user.id,
            ),
            ConversationMember(
                conversation_id=conversation.id,
                user_id=second_user.id,
            ),
        ]
    )

    await session.commit()

    other_user_id = await get_other_user_id(
        session=session,
        conversation_id=conversation.id,
        user_id=user.id,
    )

    assert other_user_id == second_user.id


@pytest.mark.asyncio
async def test_get_other_user_id_returns_none_for_non_member(
    session,
    user,
    second_user
):
    conversation = Conversation()
    session.add(conversation)
    await session.flush()

    session.add_all(
        [
            ConversationMember(
                conversation_id=conversation.id,
                user_id=user.id,
            ),
            ConversationMember(
                conversation_id=conversation.id,
                user_id=second_user.id,
            ),
        ]
    )

    await session.commit()

    third_user = User(
        username="third_user",
        email="third@example.com",
        password_hash="test_hash",
    )
    session.add(third_user)
    await session.flush()

    other_user_id = await get_other_user_id(
        session=session,
        conversation_id=conversation.id,
        user_id=third_user.id,
    )

    assert other_user_id is None


@pytest.mark.asyncio
async def test_get_other_user_id_returns_none_for_nonexistent_conversation(
    session,
    user,
):
    other_user_id = await get_other_user_id(
        session=session,
        conversation_id=uuid.uuid4(),
        user_id=user.id,
    )

    assert other_user_id is None
