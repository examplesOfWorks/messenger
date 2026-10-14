import uuid
import pytest
from sqlalchemy import select

from main import app
from app.services.auth import get_current_web_user
from db.models.users import User
from db.models.messages import Conversation, ConversationMember, Message



@pytest.mark.asyncio
async def test_messenger_redirects_unauthorized_user(web_client):
    original_override = app.dependency_overrides[get_current_web_user]

    async def override_get_current_web_user():
        return None
    
    app.dependency_overrides[get_current_web_user] = (
        override_get_current_web_user
    )

    try:
        response = await web_client.get(
            "/messenger/conversations",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/users/login"
    finally: 
        app.dependency_overrides[get_current_web_user] = (
            original_override
        )
        

@pytest.mark.asyncio
async def test_messenger_page_for_authorized_user(web_client):

    response = await web_client.get("/messenger/conversations")

    assert response.status_code == 200
    assert "Сообщения" in response.text


@pytest.mark.asyncio
async def test_messenger_page_with_selected_conversation(
    web_client,
    user,
    second_user,
    session
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

    message = Message(
        conversation_id=conversation.id,
        sender_id=second_user.id,
        text="Это тестовое сообщение.",
    )
    session.add(message)

    await session.commit()

    response = await web_client.get(
        f"/messenger/conversations/{conversation.id}"
    )

    assert response.status_code == 200
    assert "Это тестовое сообщение." in response.text


@pytest.mark.asyncio
async def test_messenger_page_for_non_member(
    web_client,
    user,
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

    original_override = app.dependency_overrides[ get_current_web_user ] 
    
    async def override_get_current_web_user(): 
        return third_user 
    
    app.dependency_overrides[get_current_web_user] = (
        override_get_current_web_user
    )

    try: 
        response = await web_client.get(
            f"/messenger/conversations/{conversation.id}"
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides[get_current_web_user] = (
            original_override
        )


@pytest.mark.asyncio
async def test_messenger_page_for_nonexistent_conversation(web_client):

    nonexistent_conversation_id = uuid.uuid4()

    response = await web_client.get(
        f"/messenger/conversations/{nonexistent_conversation_id}"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_conversation_web(
    web_client,
    user,
    second_user,
    session,
):

    response = await web_client.post(
        f"/messenger/conversations/direct/{second_user.id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/messenger/conversations/"
    )

    conversation_id = response.headers["location"].split("/")[-1]

    conversation = await session.get(
        Conversation,
        uuid.UUID(conversation_id),
    )

    assert conversation is not None

    members = await session.scalars(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation.id
        )
    )
    members = members.all()

    assert len(members) == 2
    assert {member.user_id for member in members} == {
        user.id,
        second_user.id,
    }


@pytest.mark.asyncio
async def test_create_existing_conversation_web(
    web_client,
    second_user,
    session
):

    first_response = await web_client.post(
        f"/messenger/conversations/direct/{second_user.id}",
        follow_redirects=False
    )
    
    assert first_response.status_code == 303 
    
    first_location = first_response.headers["location"] 
    
    second_response = await web_client.post(
        f"/messenger/conversations/direct/{second_user.id}", 
        follow_redirects=False
    )
    
    assert second_response.status_code == 303 
    
    second_location = second_response.headers["location"] 
    
    assert second_location == first_location
    
    result = await session.scalars(
        select(Conversation)
    ) 
    
    conversations = result.all()
    
    assert len(conversations) == 1



@pytest.mark.asyncio
async def test_create_conversation_with_self(web_client, user):

    response = await web_client.post(
        f"/messenger/conversations/direct/{user.id}",
        follow_redirects=False
    )

    assert response.status_code == 400



@pytest.mark.asyncio
async def test_create_conversation_with_nonexistent_user(web_client):
    nonexistent_user_id = 999999

    response = await web_client.post(
        f"/messenger/conversations/direct/{nonexistent_user_id}",
        follow_redirects=False,
    )

    assert response.status_code == 404