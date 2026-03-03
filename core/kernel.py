"""
JARVIS-OS Kernel — Central nervous system of the AI Operating System.
Manages all subsystems, event routing, and lifecycle.
"""

import asyncio
import logging
import signal
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

from config import load_config

logger = logging.getLogger("jarvis.kernel")


class Event:
    """Internal event for inter-subsystem communication."""
    def __init__(self, type: str, data: dict = None, source: str = "kernel"):
        self.type = type
        self.data = data or {}
        self.source = source
        self.timestamp = datetime.now().isoformat()
        self.id = f"{type}_{int(time.time() * 1000)}"


class Kernel:
    """
    The JARVIS-OS Kernel.
    Orchestrates all subsystems: agents, voice, dashboard, plugins.
    """

    def __init__(self):
        self.config = load_config()
        self.name = self.config["system"]["name"]
        self.version = self.config["system"]["version"]
        self.start_time = None
        self.running = False

        # Subsystem registry
        self.subsystems = {}
        # Event bus
        self._event_listeners = {}
        # Shared state
        self.state = {
            "status": "initializing",
            "active_agents": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "uptime": 0,
            "cpu_usage": 0,
            "memory_usage": 0,
            "notifications": [],
        }
        # Command history
        self.command_history = []

    def register_subsystem(self, name: str, subsystem):
        """Register a subsystem (agents, voice, plugins, etc.)."""
        self.subsystems[name] = subsystem
        logger.info(f"Subsystem registered: {name}")

    def on_event(self, event_type: str, callback):
        """Subscribe to kernel events."""
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(callback)

    async def emit_event(self, event: Event):
        """Emit an event to all listeners."""
        listeners = self._event_listeners.get(event.type, [])
        for callback in listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.type}: {e}")

        # Also broadcast to dashboard via websocket
        ws_manager = self.subsystems.get("websocket")
        if ws_manager:
            await ws_manager.broadcast({
                "type": "kernel_event",
                "event": {
                    "type": event.type,
                    "data": event.data,
                    "source": event.source,
                    "timestamp": event.timestamp,
                }
            })

    async def boot(self):
        """Boot sequence — initialize all subsystems."""
        self.start_time = datetime.now()
        self.running = True
        self.state["status"] = "booting"

        logger.info("=" * 60)
        logger.info(f"  {self.name} v{self.version} — Boot Sequence Initiated")
        logger.info(f"  Codename: {self.config['system']['codename']}")
        logger.info("=" * 60)

        # Initialize subsystems
        for name, subsystem in self.subsystems.items():
            try:
                if hasattr(subsystem, "initialize"):
                    await subsystem.initialize(self)
                    logger.info(f"  [OK] {name}")
            except Exception as e:
                logger.error(f"  [FAIL] {name}: {e}")

        self.state["status"] = "online"
        await self.emit_event(Event("system.boot", {"status": "online"}))
        logger.info(f"  {self.name} is ONLINE.")
        logger.info("=" * 60)

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info(f"{self.name} shutting down...")
        self.state["status"] = "shutting_down"
        await self.emit_event(Event("system.shutdown"))

        for name, subsystem in reversed(list(self.subsystems.items())):
            try:
                if hasattr(subsystem, "shutdown"):
                    await subsystem.shutdown()
                    logger.info(f"  [DOWN] {name}")
            except Exception as e:
                logger.error(f"  [ERROR] {name} shutdown: {e}")

        self.running = False
        self.state["status"] = "offline"
        logger.info(f"{self.name} offline.")

    def get_uptime(self) -> float:
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0

    def get_system_info(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "codename": self.config["system"]["codename"],
            "status": self.state["status"],
            "uptime": self.get_uptime(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "subsystems": list(self.subsystems.keys()),
            "active_agents": self.state["active_agents"],
            "tasks_completed": self.state["tasks_completed"],
        }

    async def process_command(self, command: str, source: str = "dashboard") -> dict:
        """
        Central command processor — routes commands to appropriate subsystems.
        """
        self.command_history.append({
            "command": command,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        })

        await self.emit_event(Event("command.received", {
            "command": command,
            "source": source,
        }))

        # Route to the agent manager for AI processing
        agent_manager = self.subsystems.get("agents")
        if agent_manager:
            result = await agent_manager.process(command, source=source)
            self.state["tasks_completed"] += 1
            return result

        return {"error": "Agent subsystem not available", "status": "error"}


# Singleton kernel instance
_kernel: Optional[Kernel] = None

def get_kernel() -> Kernel:
    global _kernel
    if _kernel is None:
        _kernel = Kernel()
    return _kernel
