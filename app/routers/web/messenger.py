from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.users import User

from app.services.auth import get_current_web_user
from app.services.messenger import get_user_conversations


templates = Jinja2Templates(directory="templates")

router = APIRouter(
    prefix="/messenger"
)


@router.get("/conversations", include_in_schema=False)
async def get_user_conversations_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
):
    if not current_user:
        return RedirectResponse(
            url="/users/login",
            status_code=303
        )

    conversations = await get_user_conversations(session, current_user.id)

    conversation_data = []

    for conversation in conversations:
        other_member = next(
            member
            for member in conversation.members
            if member.user_id != current_user.id
        )

        conversation_data.append({
            "id": conversation.id,
            "created_at": conversation.created_at,
            "other_user": other_member.user,
        })

    selected_conversation = None
    messages = []

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