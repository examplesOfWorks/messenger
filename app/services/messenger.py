from fastapi import HTTPException
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.messages import Conversation, ConversationMember, Message

import uuid


async def get_user_conversations(
    session: AsyncSession,
    user_id: int
):
    result_conversations = await session.scalars(
        select(Conversation)
        .options(
            selectinload(Conversation.members)
            .selectinload(ConversationMember.user)
        )
        .join(ConversationMember)
        .where(
            ConversationMember.user_id == user_id,
            exists().where(
            Message.conversation_id == Conversation.id
            )
        )
        .order_by(Conversation.created_at.desc())
    )

    conversations = result_conversations.all()

    conversation_data = []

    for conversation in conversations:
        other_member = next(
            member
            for member in conversation.members
            if member.user_id != user_id
        )

        conversation_data.append({
            "id": conversation.id,
            "created_at": conversation.created_at,
            "other_user": other_member.user,
        })

    return conversation_data


async def get_selected_conversation(
    session: AsyncSession,
    user_id: int,
    conversation_id: uuid.UUID
):
        
    member = await session.scalar( 
        select(ConversationMember).where( 
            ConversationMember.conversation_id == conversation_id, 
            ConversationMember.user_id == user_id 
        ) 
    )

    if member is None: 
        raise HTTPException( 
            status_code=403, 
            detail="Вы не являетесь участником этой беседы"
        )

    selected_conversation_obj = await session.scalar( 
        select(Conversation) 
        .options( 
            selectinload(Conversation.members) 
            .selectinload(ConversationMember.user) 
        ) 
        .where( 
            Conversation.id == conversation_id 
        ) 
    )
        
    if selected_conversation_obj is None: 
        raise HTTPException( 
            status_code=404, detail="Диалог не найден"
        )

    for member in selected_conversation_obj.members:
        if member.user_id != user_id:
            other_member = member
            break
        
    selected_conversation = {
        "id": selected_conversation_obj.id,
        "created_at": selected_conversation_obj.created_at,
        "other_user": other_member.user,
    }

    return selected_conversation


async def get_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID
): 
    result_messages = await session.scalars( 
        select(Message) 
        .where( 
            Message.conversation_id == conversation_id 
        ) 
        .order_by(Message.created_at) 
    )
        
    messages = result_messages.all()

    return messages
