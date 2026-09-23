from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.users import User

from app.services.auth import get_current_web_user
from app.services.messenger import get_user_conversations, get_selected_conversation, get_messages

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