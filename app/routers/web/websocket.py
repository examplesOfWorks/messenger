from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from app.services.websocket import manager, get_other_user_id

import uuid


router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    session: AsyncSession = Depends(get_session)
):
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


    except WebSocketDisconnect:

        is_offline = manager.disconnect(user_id, websocket)

        if is_offline:
            await manager.broadcast({
                "type": "user_status",
                "user_id": user_id,
                "status": "offline"
            })