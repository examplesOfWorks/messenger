from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.users import User
from db.models.messages import Conversation, ConversationMember

from app.services.auth import get_current_api_user


router = APIRouter(
    prefix="/api-messenger",
    tags=["Чат"],
)


@router.post("/conversations/direct/{user_id}")
async def get_or_create_conversation(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):

    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя создать диалог с самим собой",
        )

    target_user = await session.get(User, user_id)

    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден"
        )

    this_user = exists().where(
        ConversationMember.conversation_id == Conversation.id,
        ConversationMember.user_id == current_user.id,
    )

    other_user = exists().where(
        ConversationMember.conversation_id == Conversation.id,
        ConversationMember.user_id == user_id,
    )

    conversation = await session.scalar(
        select(Conversation).where(
            this_user,
            other_user
        )
    )

    if conversation is not None:
        return {"conversation_id": conversation.id}

    try:

        conversation = Conversation()

        session.add(conversation)

        await session.flush()

        session.add_all(
            [
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=current_user.id
                ),
                ConversationMember(
                    conversation_id=conversation.id,
                    user_id=user_id
                )
            ]
        )

        await session.commit()
        await session.refresh(conversation)

        return {"conversation_id": conversation.id}

    except Exception:
        await session.rollback()
        raise