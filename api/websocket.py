"""
JARVIS-OS WebSocket Manager — Real-time bidirectional communication.
"""

import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger("jarvis.ws")


class WebSocketManager:
    """Manages WebSocket connections for real-time dashboard updates."""

    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self.kernel = None

    async def initialize(self, kernel):
        self.kernel = kernel

    async def shutdown(self):
        for ws in list(self.connections):
            try:
                await ws.close()
            except Exception:
                pass
        self.connections.clear()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.add(ws)
        logger.info(f"WebSocket connected — {len(self.connections)} total")

    def disconnect(self, ws: WebSocket):
        self.connections.discard(ws)
        logger.info(f"WebSocket disconnected — {len(self.connections)} total")

    async def broadcast(self, data: dict):
        """Broadcast a message to all connected clients."""
        if not self.connections:
            return
        message = json.dumps(data, default=str)
        dead = set()
        for ws in self.connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self.connections -= dead

    async def send_to(self, ws: WebSocket, data: dict):
        """Send a message to a specific client."""
        try:
            await ws.send_text(json.dumps(data, default=str))
        except Exception:
            self.connections.discard(ws)

    async def handle_message(self, ws: WebSocket, data: dict):
        """Handle an incoming WebSocket message from a client."""
        msg_type = data.get("type")

        if msg_type == "command":
            command = data.get("command", "")
            source = data.get("source", "dashboard")

            if self.kernel:
                # Process command asynchronously
                asyncio.create_task(self._process_command(ws, command, source))

        elif msg_type == "voice_command":
            command = data.get("command", "")
            if self.kernel:
                asyncio.create_task(self._process_command(ws, command, "voice"))

        elif msg_type == "ping":
            await self.send_to(ws, {"type": "pong"})

    async def _process_command(self, ws: WebSocket, command: str, source: str):
        """Process a command and send the result back."""
        try:
            result = await self.kernel.process_command(command, source)
            await self.send_to(ws, {
                "type": "command_result",
                "result": result.get("result", ""),
                "error": result.get("error"),
                "status": result.get("status"),
                "agent_id": result.get("agent_id"),
            })
        except Exception as e:
            await self.send_to(ws, {
                "type": "command_result",
                "error": str(e),
                "status": "error",
            })
