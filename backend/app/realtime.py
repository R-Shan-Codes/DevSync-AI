import asyncio
from collections import defaultdict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.lock = asyncio.Lock()

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.connections[project_id].add(websocket)

    async def disconnect(self, project_id: str, websocket: WebSocket):
        async with self.lock:
            self.connections[project_id].discard(websocket)
            if not self.connections[project_id]:
                self.connections.pop(project_id, None)

    async def broadcast(self, project_id: str, event: dict):
        async with self.lock:
            clients = list(self.connections.get(project_id, set()))
        dead = []
        for client in clients:
            try:
                await client.send_json(event)
            except Exception:
                dead.append(client)
        for client in dead:
            await self.disconnect(project_id, client)

manager = ConnectionManager()
