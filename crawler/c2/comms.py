from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_implant_connections: Dict[str, WebSocket] = {}
        self.active_operator_connections: Dict[str, List[WebSocket]] = {}

    async def connect_implant(self, websocket: WebSocket, implant_id: str):
        await websocket.accept()
        self.active_implant_connections[implant_id] = websocket

    def disconnect_implant(self, implant_id: str):
        if implant_id in self.active_implant_connections:
            del self.active_implant_connections[implant_id]

    async def connect_operator(self, websocket: WebSocket, implant_id: str):
        await websocket.accept()
        if implant_id not in self.active_operator_connections:
            self.active_operator_connections[implant_id] = []
        self.active_operator_connections[implant_id].append(websocket)

    def disconnect_operator(self, implant_id: str, websocket: WebSocket):
        if implant_id in self.active_operator_connections:
            self.active_operator_connections[implant_id].remove(websocket)
            if not self.active_operator_connections[implant_id]:
                del self.active_operator_connections[implant_id]

    async def send_to_implant(self, message: str, implant_id: str):
        if implant_id in self.active_implant_connections:
            await self.active_implant_connections[implant_id].send_text(message)

    async def send_to_operator(self, message: str, implant_id: str):
        if implant_id in self.active_operator_connections:
            for connection in self.active_operator_connections[implant_id]:
                await connection.send_text(message)

manager = ConnectionManager()
