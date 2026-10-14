import pytest
from sqlalchemy import select

from main import app
from app.services.auth import get_current_api_user

from db.models.users import User
from db.models.messages import Conversation, ConversationMember, Message


# тест для create_conversation
@pytest.mark.asyncio
async def test_create_conversation(client, user, second_user, session):
    response = await client.post(
        f"/api-messenger/conversations/direct/{second_user.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert "conversation_id" in data

    conversation_id = data["conversation_id"]

    members = await session.scalars(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id
        )
    )

    members = members.all()

    assert len(members) == 2

    assert {member.user_id for member in members} == {
        user.id,
        second_user.id,
    }

@pytest.mark.asyncio
async def test_create_conversation_returns_existing(
    client,
    second_user,
    session
):
    first_response = await client.post(
        f"/api-messenger/conversations/direct/{second_user.id}"
    )

    assert first_response.status_code == 200

    first_conversation_id = first_response.json()["conversation_id"]

    second_response = await client.post(
        f"/api-messenger/conversations/direct/{second_user.id}"
    )

    assert second_response.status_code == 200

    second_conversation_id = second_response.json()["conversation_id"]

    assert second_conversation_id == first_conversation_id

    result = await session.scalars(
        select(Conversation)
    )

    conversations = result.all()

    assert len(conversations) == 1


@pytest.mark.asyncio
async def test_create_conversation_with_self(client, user):
    response = await client.post(
        f"/api-messenger/conversations/direct/{user.id}"
    )

    assert response.status_code == 400

    assert response.json() == {
        "detail": "Нельзя создать диалог с самим собой"
    }


@pytest.mark.asyncio
async def test_create_conversation_with_nonexistent_user(
    client
):
    nonexistent_user_id = 999999

    response = await client.post(
        f"/api-messenger/conversations/direct/{nonexistent_user_id}"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Пользователь не найден"
    }


# тесты create_message
@pytest.mark.asyncio
async def test_create_message(
    client,
    user,
    second_user,
    session
): 
    response_conversation = await client.post(
        f"/api-messenger/conversations/direct/{second_user.id}"
    )

    assert response_conversation.status_code == 200

    conversation_id = response_conversation.json()["conversation_id"]

    response_message = await client.post(
        f"/api-messenger/conversations/{conversation_id}/messages",
        json={
            "text": "Привет!"
        },
    )

    assert response_message.status_code == 200

    data = response_message.json()

    assert data["conversation_id"] == conversation_id
    assert data["sender_id"] == user.id
    assert data["text"] == "Привет!"

    message = await session.scalar(
        select(Message).where(
            Message.conversation_id == conversation_id
        )
    )

    assert message is not None
    assert message.sender_id == user.id
    assert message.text == "Привет!"


@pytest.mark.asyncio
async def test_create_message_for_non_member(
    client,
    second_user,
    session
):
    third_user = User(
        username="third_user",
        email="third@example.com",
        password_hash="test_hash",
    )

    session.add(third_user)
    await session.flush()

    response = await client.post(
        f"/api-messenger/conversations/direct/{second_user.id}"
    )

    assert response.status_code == 200

    conversation_id = response.json()["conversation_id"]

    original_override = app.dependency_overrides[get_current_api_user]
     
    async def override_get_current_api_user():
        return third_user

    app.dependency_overrides[get_current_api_user] = (
        override_get_current_api_user
    )

    try:
        response = await client.post(
            f"/api-messenger/conversations/{conversation_id}/messages",
            json={
                "text": "Я не должен иметь доступ"
            },
        )

        assert response.status_code == 403

        assert response.json() == {
            "detail": "Вы не являетесь участником этой беседы"
        }
    finally: 
        app.dependency_overrides[get_current_api_user] = (original_override)