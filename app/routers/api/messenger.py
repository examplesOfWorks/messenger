from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import get_session
from db.models.users import User
from db.models.messages import Conversation, ConversationMember, Message

from app.services.auth import get_current_api_user
from app.schemas.messenger import ConversationUserResponse, ConversationResponse, MessageCreate, MessageResponse

import uuid


router = APIRouter(
    prefix="/api-messenger",
    tags=["Чат"],
)


@router.get("/conversations/direct")
async def get_user_conversations(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):
    result = await session.scalars(
        select(Conversation)
        .options(
            selectinload(Conversation.members)
            .selectinload(ConversationMember.user)
        )
        .join(ConversationMember)
        .where(
            ConversationMember.user_id == current_user.id
        )
        .order_by(Conversation.created_at.desc())
    )

    conversations = result.all()

    response = []

    for conversation in conversations:
        other_member = next(
            member
            for member in conversation.members
            if member.user_id != current_user.id
        )

        response.append(
            ConversationResponse(
                id=conversation.id,
                created_at=conversation.created_at,
                other_user=ConversationUserResponse(
                    id=other_member.user.id,
                    username=other_member.user.username,
                    photo=other_member.user.photo,
                ),
            )
        )

    return response


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversations_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):

    member = await session.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == current_user.id
        )
    )

    if member is None:
        raise HTTPException(
            status_code=403,
            detail="Вы не являетесь участником этой беседы"
        )

    result = await session.execute( 
        select(Message).where(
            Message.conversation_id == conversation_id,
        )
    )

    messages = result.scalars().all()
    
    return messages


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


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def create_message(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):
    target_conversation = await session.get(Conversation, conversation_id)

    if target_conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Диалог не найден"
        ) 

    member = await session.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == current_user.id
        )
    )

    if member is None:
        raise HTTPException(
            status_code=403,
            detail="Вы не являетесь участником этой беседы"
        )

    try:

        message = Message(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            text=data.text
        )

        session.add(message)

        await session.commit()
        await session.refresh(message)

        return message

    except Exception:
        await session.rollback()
        raise