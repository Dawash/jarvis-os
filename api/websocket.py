"""
JARVIS-OS WebSocket Manager — Real-time bidirectional communication.
Handles streaming agent progress, task plans, tool execution updates,
barge-in, reminders, and dialogue state.
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
        # Start reminder checker
        asyncio.create_task(self._reminder_checker())

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
        try:
            await ws.send_text(json.dumps(data, default=str))
        except Exception:
            self.connections.discard(ws)

    async def handle_message(self, ws: WebSocket, data: dict):
        msg_type = data.get("type")

        if msg_type == "command":
            command = data.get("command", "")
            source = data.get("source", "dashboard")
            if self.kernel:
                asyncio.create_task(self._process_command(ws, command, source))

        elif msg_type == "voice_command":
            command = data.get("command", "")
            if self.kernel:
                asyncio.create_task(self._process_command(ws, command, "voice"))

        elif msg_type == "barge_in":
            if self.kernel:
                ve = self.kernel.subsystems.get("voice")
                if ve:
                    ve.barge_in()
                    await self.send_to(ws, {"type": "barge_in_ack"})
                await self.broadcast({"type": "stop_speaking"})

        elif msg_type == "cancel_agent":
            agent_id = data.get("agent_id")
            if self.kernel and agent_id:
                am = self.kernel.subsystems.get("agents")
                if am:
                    am.cancel_agent(agent_id)
                    await self.send_to(ws, {"type": "agent_cancelled", "agent_id": agent_id})

        elif msg_type == "undo":
            if self.kernel:
                ah = self.kernel.subsystems.get("action_history")
                if ah:
                    result = await ah.undo_last()
                    await self.send_to(ws, {"type": "undo_result", **result})

        elif msg_type == "get_briefing":
            if self.kernel:
                gm = self.kernel.subsystems.get("goals")
                if gm:
                    await self.send_to(ws, {"type": "briefing", "text": gm.generate_briefing()})

        elif msg_type == "ping":
            await self.send_to(ws, {"type": "pong"})

    async def _process_command(self, ws: WebSocket, command: str, source: str):
        try:
            await self.send_to(ws, {
                "type": "command_accepted",
                "command": command,
                "status": "processing",
            })

            result = await self.kernel.process_command(command, source)

            # Handle special actions
            if result.get("action") == "undo":
                ah = self.kernel.subsystems.get("action_history")
                if ah:
                    undo_result = await ah.undo_last()
                    result["result"] = undo_result.get("message", "Nothing to undo")

            await self.send_to(ws, {
                "type": "command_result",
                "result": result.get("result", ""),
                "error": result.get("error"),
                "status": result.get("status"),
                "agent_id": result.get("agent_id"),
                "plan": result.get("plan"),
                "steps_taken": len(result.get("steps", [])) if "steps" in result else 0,
            })
        except Exception as e:
            await self.send_to(ws, {
                "type": "command_result",
                "error": str(e),
                "status": "error",
            })

    async def _reminder_checker(self):
        """Periodically check for due reminders and broadcast them."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                if not self.kernel:
                    continue
                pm = self.kernel.subsystems.get("plugins")
                if not pm or "reminders" not in pm.plugins:
                    continue
                module = pm.plugins["reminders"].get("module")
                if not module or not hasattr(module, "get_due_reminders"):
                    continue
                due = module.get_due_reminders()
                for reminder in due:
                    await self.broadcast({
                        "type": "reminder",
                        "message": reminder.get("message", ""),
                        "id": reminder.get("id", ""),
                        "time": reminder.get("time", ""),
                    })
            except Exception:
                pass
