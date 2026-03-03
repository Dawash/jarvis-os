"""
JARVIS-OS Action History — Undo/Reversibility system.
Every tool execution is logged with a reversibility flag.
Supports undo for file operations, process actions, and more.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.action_history")


class ActionHistory:
    """Tracks all agent actions with undo capability."""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / "action_history.json"
        self.actions: list[dict] = self._load()
        self.kernel = None

    def _load(self) -> list:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                return []
        return []

    def _save(self):
        # Keep last 500 actions
        if len(self.actions) > 500:
            self.actions = self.actions[-500:]
        self._file.write_text(json.dumps(self.actions, indent=2, default=str))

    async def initialize(self, kernel):
        self.kernel = kernel

    async def shutdown(self):
        self._save()

    def record(self, tool: str, args: dict, result: str, reversible: bool = False,
               undo_action: dict = None, agent_id: str = None):
        """Record an action in the history."""
        entry = {
            "id": f"act_{int(datetime.now().timestamp() * 1000)}",
            "tool": tool,
            "args": args,
            "result": result[:500],
            "reversible": reversible,
            "undo_action": undo_action,
            "agent_id": agent_id,
            "undone": False,
            "timestamp": datetime.now().isoformat(),
        }
        self.actions.append(entry)
        self._save()
        return entry["id"]

    def get_last_reversible(self) -> Optional[dict]:
        """Get the most recent reversible action that hasn't been undone."""
        for action in reversed(self.actions):
            if action.get("reversible") and not action.get("undone"):
                return action
        return None

    async def undo_last(self) -> dict:
        """Undo the most recent reversible action."""
        action = self.get_last_reversible()
        if not action:
            return {"status": "error", "message": "No reversible action to undo"}

        undo = action.get("undo_action")
        if not undo:
            return {"status": "error", "message": "Action has no undo definition"}

        try:
            result = await self._execute_undo(undo)
            action["undone"] = True
            action["undone_at"] = datetime.now().isoformat()
            self._save()

            logger.info(f"Undid action: {action['tool']} ({action['id']})")
            return {
                "status": "success",
                "message": f"Undid: {action['tool']} — {undo.get('description', '')}",
                "original_action": action["tool"],
                "original_args": action["args"],
            }
        except Exception as e:
            return {"status": "error", "message": f"Undo failed: {str(e)}"}

    async def _execute_undo(self, undo: dict) -> str:
        """Execute an undo action."""
        undo_type = undo.get("type")
        sc = self.kernel.subsystems.get("system_control") if self.kernel else None

        if undo_type == "restore_file" and sc:
            # Restore file content from backup
            path = undo["path"]
            content = undo["original_content"]
            Path(path).write_text(content)
            return f"Restored {path}"

        elif undo_type == "delete_file" and sc:
            path = undo["path"]
            p = Path(path)
            if p.exists():
                p.unlink()
            return f"Deleted {path}"

        elif undo_type == "move_file" and sc:
            import shutil
            shutil.move(undo["current_path"], undo["original_path"])
            return f"Moved back to {undo['original_path']}"

        elif undo_type == "shell_command" and sc:
            import asyncio
            proc = await asyncio.create_subprocess_shell(
                undo["command"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return stdout.decode()

        elif undo_type == "create_directory":
            import shutil
            path = undo["path"]
            if Path(path).exists():
                shutil.rmtree(path)
            return f"Removed directory {path}"

        else:
            return f"Unknown undo type: {undo_type}"

    def get_history(self, limit: int = 50) -> list:
        return self.actions[-limit:]

    def get_reversible_actions(self, limit: int = 20) -> list:
        reversible = [a for a in self.actions if a.get("reversible") and not a.get("undone")]
        return reversible[-limit:]

    # ── Helper: determine undo for common operations ─────────────

    @staticmethod
    def make_file_write_undo(path: str, original_content: str = None) -> dict:
        """Create undo info for a file write operation."""
        if original_content is not None:
            return {
                "type": "restore_file", "path": path,
                "original_content": original_content,
                "description": f"Restore original content of {path}",
            }
        return {
            "type": "delete_file", "path": path,
            "description": f"Delete newly created file {path}",
        }

    @staticmethod
    def make_file_move_undo(original_path: str, new_path: str) -> dict:
        return {
            "type": "move_file", "original_path": original_path,
            "current_path": new_path,
            "description": f"Move back from {new_path} to {original_path}",
        }

    @staticmethod
    def make_shell_undo(command: str, description: str = "") -> dict:
        return {
            "type": "shell_command", "command": command,
            "description": description or f"Run: {command}",
        }
