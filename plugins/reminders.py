"""
JARVIS-OS Plugin: Reminders & Scheduling
Set reminders, recurring tasks, and scheduled actions using APScheduler.
Persistent job store survives restarts.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.plugin.reminders")

PLUGIN_INFO = {
    "name": "Reminders & Scheduling",
    "version": "1.0.0",
    "description": "Set reminders, recurring tasks, and scheduled actions",
    "author": "JARVIS-OS",
    "capabilities": ["reminders", "scheduling", "recurring_tasks"],
}

# In-memory store (persisted to JSON)
_reminders: list[dict] = []
_data_file: Optional[Path] = None
_kernel = None


def _load():
    global _reminders
    if _data_file and _data_file.exists():
        try:
            _reminders = json.loads(_data_file.read_text())
        except Exception:
            _reminders = []


def _save():
    if _data_file:
        _data_file.write_text(json.dumps(_reminders, indent=2, default=str))


def get_tools():
    return [
        {
            "name": "set_reminder",
            "description": "Set a reminder for a specific time. Supports natural time like '3pm', 'in 30 minutes', '2024-12-25 09:00'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "What to remind about"},
                    "time": {"type": "string", "description": "When to remind (e.g., 'in 30 minutes', '3pm', '2024-12-25 09:00')"},
                    "recurring": {"type": "string", "description": "Recurrence: 'daily', 'weekly', 'monthly', or empty for one-time"},
                },
                "required": ["message", "time"],
            },
        },
        {
            "name": "list_reminders",
            "description": "List all active reminders.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "cancel_reminder",
            "description": "Cancel a reminder by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "The reminder ID to cancel"},
                },
                "required": ["reminder_id"],
            },
        },
    ]


def _parse_time(time_str: str) -> Optional[datetime]:
    """Parse natural time expressions to datetime."""
    time_str = time_str.strip().lower()
    now = datetime.now()

    # Relative times
    if time_str.startswith("in "):
        parts = time_str[3:].split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
            except ValueError:
                return None
            unit = parts[1].rstrip("s")
            if unit == "minute":
                return now + timedelta(minutes=amount)
            elif unit == "hour":
                return now + timedelta(hours=amount)
            elif unit == "day":
                return now + timedelta(days=amount)
            elif unit == "week":
                return now + timedelta(weeks=amount)

    # Time-only (today)
    for fmt in ["%I%p", "%I:%M%p", "%H:%M"]:
        try:
            parsed = datetime.strptime(time_str, fmt)
            result = now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
            if result < now:
                result += timedelta(days=1)
            return result
        except ValueError:
            continue

    # Full datetime
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y"]:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    # Tomorrow
    if "tomorrow" in time_str:
        return now + timedelta(days=1)

    return None


async def execute(tool_name: str, arguments: dict, context: dict) -> dict:
    if tool_name == "set_reminder":
        return await _set_reminder(arguments.get("message", ""), arguments.get("time", ""),
                                    arguments.get("recurring", ""))
    elif tool_name == "list_reminders":
        return _list_reminders()
    elif tool_name == "cancel_reminder":
        return _cancel_reminder(arguments.get("reminder_id", ""))
    return {"error": f"Unknown tool: {tool_name}"}


async def _set_reminder(message: str, time_str: str, recurring: str = "") -> dict:
    reminder_time = _parse_time(time_str)
    if not reminder_time:
        return {"status": "error", "message": f"Could not parse time: '{time_str}'"}

    reminder = {
        "id": f"rem_{int(datetime.now().timestamp() * 1000)}",
        "message": message,
        "time": reminder_time.isoformat(),
        "recurring": recurring or None,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "fired": False,
    }
    _reminders.append(reminder)
    _save()

    # Schedule with APScheduler if available
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        # Scheduling happens in the kernel's scheduler
    except ImportError:
        pass

    time_str_friendly = reminder_time.strftime("%B %d at %I:%M %p")
    return {
        "status": "success",
        "reminder_id": reminder["id"],
        "message": f"Reminder set: '{message}' for {time_str_friendly}",
        "time": reminder_time.isoformat(),
        "recurring": recurring or "one-time",
    }


def _list_reminders() -> dict:
    active = [r for r in _reminders if r.get("status") == "active"]
    return {
        "status": "success",
        "count": len(active),
        "reminders": active,
    }


def _cancel_reminder(reminder_id: str) -> dict:
    for r in _reminders:
        if r["id"] == reminder_id:
            r["status"] = "cancelled"
            _save()
            return {"status": "success", "message": f"Reminder {reminder_id} cancelled"}
    return {"status": "error", "message": f"Reminder not found: {reminder_id}"}


def get_due_reminders() -> list:
    """Check for reminders that are due (called by scheduler)."""
    now = datetime.now()
    due = []
    for r in _reminders:
        if r.get("status") != "active" or r.get("fired"):
            continue
        try:
            remind_time = datetime.fromisoformat(r["time"])
            if remind_time <= now:
                due.append(r)
                if r.get("recurring"):
                    # Reschedule
                    delta = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1),
                             "monthly": timedelta(days=30)}.get(r["recurring"], timedelta(days=1))
                    r["time"] = (remind_time + delta).isoformat()
                else:
                    r["fired"] = True
                    r["status"] = "completed"
        except (ValueError, TypeError):
            continue
    if due:
        _save()
    return due


async def on_load(kernel):
    global _data_file, _kernel
    _kernel = kernel
    data_dir = Path(kernel.config.get("system", {}).get("data_dir", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    _data_file = data_dir / "reminders.json"
    _load()
    logger.info(f"Reminders plugin loaded — {len([r for r in _reminders if r.get('status') == 'active'])} active")


async def on_unload():
    _save()
    logger.info("Reminders plugin unloaded")
