from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.users import User
from db.models.messages import Conversation, ConversationMember, Message

from app.services.auth import get_current_web_user
from app.services.messenger import get_user_conversations, get_selected_conversation, get_messages, dialogue_existence

import uuid



templates = Jinja2Templates(directory="templates")

router = APIRouter(
    prefix="/messenger"
)


@router.get("/conversations", include_in_schema=False)
@router.get("/conversations/{conversation_id}", include_in_schema=False)
async def get_user_conversations_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    conversation_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_web_user)
):
    if not current_user:
        return RedirectResponse(
            url="/users/login",
            status_code=303
        )

    conversation_data = await get_user_conversations(session, current_user.id)

    selected_conversation = None
    messages = []

    if conversation_id is not None:
        selected_conversation = await get_selected_conversation(session, current_user.id, conversation_id)

        messages = await get_messages(session, conversation_id)

    return templates.TemplateResponse(
        request=request,
        name="messenger/conversations.html",
        context={
            "current_user": current_user,
            "conversations": conversation_data,
            "selected_conversation": selected_conversation,
            "messages": messages,
        }
    )

@router.post("/conversations/direct/{user_id}", include_in_schema=False)
async def get_or_create_conversation(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
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
    
    conversation = await dialogue_existence(session, current_user.id, user_id)

    if conversation is not None:
        return RedirectResponse(
            f"/messenger/conversations/{conversation.id}",
            status_code=303
        )
    
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

        return RedirectResponse(
            f"/messenger/conversations/{conversation.id}",
            status_code=303
        )

    except Exception:
        await session.rollback()
        raise


@router.post("/conversations/{conversation_id}/messages", include_in_schema=False)
async def create_message(
    conversation_id: uuid.UUID,
    text: str = Form(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
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
            text=text
        )

        session.add(message)

        await session.commit()
        await session.refresh(message)

        return RedirectResponse(
            f"/messenger/conversations/{conversation_id}",
            status_code=303
        )

    except Exception:
        await session.rollback()
        raise