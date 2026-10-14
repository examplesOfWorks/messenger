import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from db.models.users import User
from db.models.messages import Conversation, ConversationMember, Message
from app.services.messenger import create_message, get_unread_count, dialogue_existence, get_messages, get_total_unread_count, get_selected_conversation, get_user_conversations



# тесты для create_message
@pytest.mark.asyncio
async def test_create_message_for_member(session, user):

    conversation = Conversation()

    session.add(user)
    session.add(conversation)

    await session.flush()

    member = ConversationMember(
        conversation_id=conversation.id,
        user_id=user.id,
    )

    session.add(member)

    await session.commit()

    message = await create_message(
        session=session,
        conversation_id=conversation.id,
        user_id=user.id,
        text="Привет!",
    )

    assert message.id is not None
    assert message.conversation_id == conversation.id
    assert message.sender_id == user.id
    assert message.text == "Привет!"


@pytest.mark.asyncio
async def test_create_message_for_non_member(session, user, second_user):

    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

    await session.flush()

    member = ConversationMember(
        conversation_id=conversation.id,
        user_id=user.id,
    )

    session.add(member)

    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await create_message(
            session=session,
            conversation_id=conversation.id,
            user_id=second_user.id,
            text="Я не должен это отправить",
        )

    assert exc_info.value.status_code == 403


# тесты для get_user_conversations
@pytest.mark.asyncio
async def test_get_user_conversations_returns_user_conversations(
    session,
    user,
    second_user
):

    third_user = User(
        username="third_user",
        email="third@example.com",
        password_hash="test_hash",
    )

    conversation_one = Conversation()
    conversation_two = Conversation()

    session.add_all([
        user,
        second_user,
        third_user,
        conversation_one,
        conversation_two,
    ])

    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=conversation_two.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation_two.id,
            user_id=third_user.id,
        ),
    ])

    session.add_all([
        Message(
            conversation_id=conversation_one.id,
            sender_id=second_user.id,
            text="Сообщение в первом диалоге",
        ),
        Message(
            conversation_id=conversation_two.id,
            sender_id=third_user.id,
            text="Сообщение во втором диалоге",
        ),
    ])

    await session.commit()

    conversations = await get_user_conversations(
        session=session,
        user_id=user.id,
    )

    assert len(conversations) == 2

    conversation_ids = {
        conversation["id"]
        for conversation in conversations
    }

    assert conversation_ids == {
        conversation_one.id,
        conversation_two.id,
    }


@pytest.mark.asyncio
async def test_get_user_conversations_returns_unread_count(
    session,
    user,
    second_user
):
    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

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

    session.add_all([
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Непрочитанное 1",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Непрочитанное 2",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Прочитанное",
            read_at=datetime.now(timezone.utc),
        ),
    ])

    await session.commit()

    conversations = await get_user_conversations(
        session=session,
        user_id=user.id,
    )

    assert len(conversations) == 1
    assert conversations[0]["unread_count"] == 2


@pytest.mark.asyncio
async def test_get_user_conversations_ignores_own_messages(
    session,
    user,
    second_user
):
    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

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

    session.add_all([
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Сообщение от другого пользователя",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=user.id,
            text="Моё сообщение",
        ),
    ])

    await session.commit()

    conversations = await get_user_conversations(
        session=session,
        user_id=user.id,
    )

    assert len(conversations) == 1
    assert conversations[0]["unread_count"] == 1


@pytest.mark.asyncio
async def test_get_user_conversations_ignores_empty_conversations(
    session,
    user,
    second_user
):

    conversation_with_message = Conversation()
    empty_conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation_with_message,
        empty_conversation,
    ])
    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation_with_message.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation_with_message.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=empty_conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=empty_conversation.id,
            user_id=second_user.id,
        ),
    ])

    session.add(
        Message(
            conversation_id=conversation_with_message.id,
            sender_id=second_user.id,
            text="Сообщение",
        )
    )

    await session.commit()

    conversations = await get_user_conversations(
        session=session,
        user_id=user.id,
    )

    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation_with_message.id


# тесты для get_selected_conversation
@pytest.mark.asyncio
async def test_get_selected_conversation_for_member(
    session,
    user,
    second_user
):
    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

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

    await session.commit()

    selected_conversation = await get_selected_conversation(
        session=session,
        user_id=user.id,
        conversation_id=conversation.id,
    )

    assert selected_conversation is not None
    assert selected_conversation["id"] == conversation.id


@pytest.mark.asyncio
async def test_get_selected_conversation_returns_other_user(
    session,
    user,
    second_user
):
    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

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

    await session.commit()

    selected_conversation = await get_selected_conversation(
        session=session,
        user_id=user.id,
        conversation_id=conversation.id,
    )

    assert selected_conversation["other_user"].id == second_user.id


@pytest.mark.asyncio
async def test_get_selected_conversation_for_non_member(
    session,
    user,
    second_user
):
    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

    await session.flush()

    session.add(
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        )
    )

    await session.commit() 

    with pytest.raises(HTTPException) as exc_info:
        await get_selected_conversation(
            session=session,
            user_id=user.id,
            conversation_id=conversation.id,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_selected_conversation_for_nonexistent_conversation(
    session,
    user
):

    session.add(user)
    await session.flush()

    nonexistent_conversation_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await get_selected_conversation(
            session=session,
            user_id=user.id,
            conversation_id=nonexistent_conversation_id,
        )

    assert exc_info.value.status_code == 404

# тесты для get_messages
@pytest.mark.asyncio
async def test_get_messages_returns_messages_in_order(
    session,
    user,
    second_user
):
    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

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

    message_one = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        text="Первое сообщение",
    )

    message_two = Message(
        conversation_id=conversation.id,
        sender_id=second_user.id,
        text="Второе сообщение",
    )

    message_three = Message(
        conversation_id=conversation.id,
        sender_id=user.id,
        text="Третье сообщение",
    )

    session.add_all([
        message_one,
        message_two,
        message_three,
    ])

    await session.commit()

    messages = await get_messages(
        session=session,
        conversation_id=conversation.id,
    )

    assert len(messages) == 3
    assert messages[0].text == "Первое сообщение"
    assert messages[1].text == "Второе сообщение"
    assert messages[2].text == "Третье сообщение"


@pytest.mark.asyncio
async def test_get_messages_returns_only_messages_from_selected_conversation(
    session,
    user,
    second_user
):
    conversation_one = Conversation()
    conversation_two = Conversation()

    session.add_all([
        user,
        second_user,
        conversation_one,
        conversation_two,
    ])

    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=second_user.id,
        ),
    ])

    message_one = Message(
        conversation_id=conversation_one.id,
        sender_id=user.id,
        text="Сообщение из первого диалога",
    )

    message_two = Message(
        conversation_id=conversation_two.id,
        sender_id=second_user.id,
        text="Сообщение из второго диалога",
    )

    session.add_all([
        message_one,
        message_two,
    ])

    await session.commit()

    messages = await get_messages(
        session=session,
        conversation_id=conversation_one.id,
    )

    assert len(messages) == 1
    assert messages[0].id == message_one.id
    assert messages[0].text == "Сообщение из первого диалога"


@pytest.mark.asyncio
async def test_get_messages_returns_empty_list_for_empty_conversation(
    session,
    user
):
    conversation = Conversation()

    session.add_all([
        user,
        conversation,
    ])

    await session.flush()

    session.add(
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        )
    )

    await session.commit()

    messages = await get_messages(
        session=session,
        conversation_id=conversation.id,
    )

    assert messages == []


# тесты для dialogue_existence
@pytest.mark.asyncio
async def test_dialogue_existence(session, user, second_user):

    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

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

    await session.commit()

    result = await dialogue_existence(
        session=session,
        user_id=user.id,
        target_user_id=second_user.id,
    )

    assert result is not None
    assert result.id == conversation.id


@pytest.mark.asyncio
async def test_dialogue_existence_returns_none_when_dialogue_does_not_exist(
    session,
    user,
    second_user
):

    session.add_all([
        user,
        second_user,
    ])

    await session.commit()

    result = await dialogue_existence(
        session=session,
        user_id=user.id,
        target_user_id=second_user.id,
    )

    assert result is None


@pytest.mark.asyncio
async def test_dialogue_existence_returns_none_for_different_dialogues(
    session,
    user,
    second_user
):
    third_user = User(
        username="third_user",
        email="third@example.com",
        password_hash="test_hash",
    )

    conversation_one = Conversation()
    conversation_two = Conversation()

    session.add_all([
        user,
        second_user,
        third_user,
        conversation_one,
        conversation_two,
    ])

    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=third_user.id,
        ),
        ConversationMember(
            conversation_id=conversation_two.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=conversation_two.id,
            user_id=third_user.id,
        ),
    ])

    await session.commit()

    result = await dialogue_existence(
        session=session,
        user_id=user.id,
        target_user_id=second_user.id,
    )

    assert result is None

# тесты для get_unread_count
@pytest.mark.asyncio
async def test_get_unread_count(session, user, second_user):
    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation,
    ])

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

    await session.commit()

    session.add_all([
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Непрочитанное 1",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Непрочитанное 2",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Прочитанное",
            read_at=datetime.now(timezone.utc),
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=user.id,
            text="Моё сообщение",
        ),
    ])

    await session.commit()

    unread_count = await get_unread_count(
        session=session,
        conversation_id=conversation.id,
        user_id=user.id,
    )

    assert unread_count == 2

# тесты для get_total_unread_count
@pytest.mark.asyncio
async def test_get_total_unread_count_counts_unread_messages_from_all_conversations(
    session,
    user,
    second_user
):
    conversation_one = Conversation()
    conversation_two = Conversation()

    session.add_all([
        user,
        second_user,
        conversation_one,
        conversation_two,
    ])

    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation_one.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=conversation_two.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation_two.id,
            user_id=second_user.id,
        ),
    ])

    session.add_all([
        Message(
            conversation_id=conversation_one.id,
            sender_id=second_user.id,
            text="Непрочитанное 1",
        ),
        Message(
            conversation_id=conversation_one.id,
            sender_id=second_user.id,
            text="Непрочитанное 2",
        ),
        Message(
            conversation_id=conversation_two.id,
            sender_id=second_user.id,
            text="Непрочитанное 3",
        ),
    ])

    await session.commit()

    unread_count = await get_total_unread_count(
        session=session,
        user_id=user.id,
    )

    assert unread_count == 3


@pytest.mark.asyncio
async def test_get_total_unread_count_ignores_own_and_read_messages(
    session,
    user,
    second_user
):

    conversation = Conversation()

    session.add_all([
        user,
        second_user,
        conversation
    ])

    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=conversation.id,
            user_id=second_user.id,
        )
    ])

    session.add_all([
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Непрочитанное",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=user.id,
            text="Моё сообщение",
        ),
        Message(
            conversation_id=conversation.id,
            sender_id=second_user.id,
            text="Прочитанное",
            read_at=datetime.now(timezone.utc),
        )
    ])

    await session.commit()

    unread_count = await get_total_unread_count(
        session=session,
        user_id=user.id,
    )

    assert unread_count == 1

@pytest.mark.asyncio
async def test_get_total_unread_count_ignores_foreign_conversations(
    session,
    user,
    second_user
):
    third_user = User(
        username="third_user",
        email="third@example.com",
        password_hash="test_hash",
    )

    user_conversation = Conversation()
    foreign_conversation = Conversation()

    session.add_all([
        user,
        second_user,
        third_user,
        user_conversation,
        foreign_conversation,
    ])

    await session.flush()

    session.add_all([
        ConversationMember(
            conversation_id=user_conversation.id,
            user_id=user.id,
        ),
        ConversationMember(
            conversation_id=user_conversation.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=foreign_conversation.id,
            user_id=second_user.id,
        ),
        ConversationMember(
            conversation_id=foreign_conversation.id,
            user_id=third_user.id,
        ),
    ])

    session.add_all([
        Message(
            conversation_id=user_conversation.id,
            sender_id=second_user.id,
            text="Сообщение для меня",
        ),
        Message(
            conversation_id=foreign_conversation.id,
            sender_id=second_user.id,
            text="Чужое сообщение",
        ),
    ])

    await session.commit()

    unread_count = await get_total_unread_count(
        session=session,
        user_id=user.id,
    )

    assert unread_count == 1