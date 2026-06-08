import json
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        await self.send_personal_message({"type": "system", "event": "connected"}, websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            print(f"[WS] Send error: {e}")
            await self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        async with self._lock:
            connections = self.active_connections.copy()
        
        tasks = [self.send_personal_message(message, conn) for conn in connections]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_message(self, websocket: WebSocket, data: str):
        try:
            payload = json.loads(data)
            action = payload.get("action")
            # Routing akan dikembangkan di batch selanjutnya
            print(f"[WS] Received action: {action}")
        except json.JSONDecodeError:
            await self.send_personal_message({"type": "error", "message": "Invalid JSON format"}, websocket)
        except Exception as e:
            await self.send_personal_message({"type": "error", "message": str(e)}, websocket)