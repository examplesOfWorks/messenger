from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.messages import Message

from app.services.auth import get_websocket_user_id
from app.services.messenger import create_message
from app.services.websocket import manager, get_other_user_id

from datetime import datetime, timezone
import uuid



router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    session: AsyncSession = Depends(get_session)
):  
    try:
        authenticated_user_id = await get_websocket_user_id(websocket)
    except HTTPException:
        await websocket.close(code=1008)
        return

    if authenticated_user_id != user_id:
        await websocket.close(code=1008)
        return
    
    was_online = manager.is_online(user_id)

    await manager.connect(user_id, websocket)

    await manager.send_online_users(websocket)

    if not was_online:
        await manager.broadcast({
            "type": "user_status",
            "user_id": user_id,
            "status": "online"
        })

    try:
        while True:
            data = await websocket.receive_json()

            event_type = data.get("type")

            if event_type == "send_message":
                try:
                    authenticated_user_id = await get_websocket_user_id(websocket)
                except HTTPException:
                    await websocket.send_json({
                        "type": "auth_expired",
                    })
                    await websocket.close(code=1008)
                    return

                if authenticated_user_id != user_id:
                    await websocket.send_json({
                        "type": "auth_expired",
                    })
                    await websocket.close(code=1008)
                    return

                try:
                    conversation_id = uuid.UUID(data.get("conversation_id"))
                except (ValueError, TypeError):
                    continue

                text = data.get("text", "").strip()

                if not text:
                    continue

                try:
                    message = await create_message(
                        session=session,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        text=text,
                    )

                except HTTPException as exc:
                    await websocket.send_json({
                        "type": "error",
                        "message": exc.detail,
                    })
                    continue

                other_user_id = await get_other_user_id(
                    session,
                    conversation_id,
                    user_id,
                )

                message_data = {
                    "type": "new_message",
                    "message": {
                        "id": message.id,
                        "conversation_id": str(message.conversation_id),
                        "sender_id": message.sender_id,
                        "text": message.text,
                        "created_at": message.created_at.isoformat(),
                    },
                }

                await manager.send_to_user(
                    user_id,
                    message_data,
                )

                if other_user_id is not None:
                    await manager.send_to_user(
                        other_user_id,
                        message_data,
                    )

                continue

            if event_type == "typing":

                try:
                    conversation_id = uuid.UUID(
                        data.get("conversation_id")
                    )
                except (ValueError, TypeError):
                    continue

                is_typing = data.get("is_typing")

                other_user_id = await get_other_user_id(
                    session,
                    conversation_id,
                    user_id,
                )

                if other_user_id is None:
                    continue

                await manager.send_to_user(
                    other_user_id,
                    {
                        "type": "typing",
                        "conversation_id": str(conversation_id),
                        "user_id": user_id,
                        "is_typing": is_typing,
                    },
                )

            elif event_type == "message_read":

                try:
                    message_id = data.get("message_id")
                    conversation_id = uuid.UUID(
                        data.get("conversation_id")
                    )
                except (ValueError, TypeError):
                    continue

                message = await session.scalar(
                    select(Message).where(
                        Message.id == message_id,
                        Message.conversation_id == conversation_id,
                    )
                )

                if message is None:
                    continue

                other_user_id = await get_other_user_id(
                    session,
                    conversation_id,
                    user_id,
                )

                if other_user_id is None:
                    continue

                if message.sender_id == user_id:
                    continue

                if message.read_at is not None:
                    continue

                message.read_at = datetime.now(timezone.utc)

                await session.commit()

                await manager.send_to_user(
                    message.sender_id,
                    {
                        "type": "message_read",
                        "conversation_id": str(conversation_id),
                        "message_id": message.id,
                        "user_id": user_id,
                    },
                )

    except WebSocketDisconnect:

        is_offline = manager.disconnect(user_id, websocket)

        if is_offline:
            await manager.broadcast({
                "type": "user_status",
                "user_id": user_id,
                "status": "offline"
            })