from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.messages import Conversation, ConversationMember, Message


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

    result = result_conversations.all()

    return result