from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.websocket import manager

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int
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
            await websocket.receive_text()

    except WebSocketDisconnect:

        is_offline = manager.disconnect(user_id, websocket)

        if is_offline:
            await manager.broadcast({
                "type": "user_status",
                "user_id": user_id,
                "status": "offline"
            })