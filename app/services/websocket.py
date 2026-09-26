from fastapi import FastAPI, WebSocket


app = FastAPI()


class ConnectionManager:

    def __init__(self):
        self.active_connections: dict[int, set[WebSocket]] = {}

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket
    ):
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)

    def disconnect(
        self,
        user_id: int, 
        websocket: WebSocket
    ):
        connections = self.active_connections.get(user_id)

        if not connections:
            return False

        connections.discard(websocket)

        if not connections:
            del self.active_connections[user_id]
            return True

        return False
        
    def is_online(self, user_id: int):
        return user_id in self.active_connections
    
    async def send_online_users(
        self,
        websocket: WebSocket,
    ):
        online_users = list(self.active_connections.keys())

        await websocket.send_json({
            "type": "online_users",
            "user_ids": online_users,
        })
    
    async def broadcast(self, data:dict):
        for connections in self.active_connections.values():
            for websocket in connections.copy():
                await websocket.send_json(data)


manager = ConnectionManager()