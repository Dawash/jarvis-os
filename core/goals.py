"""
JARVIS-OS Goal-Driven Task System — Persistent goals with progress tracking.
Supports morning briefings, milestone tracking, and deadline awareness.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.goals")


class GoalManager:
    """Manages persistent goals with milestones and progress tracking."""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.data_dir / "goals.json"
        self.goals: list[dict] = self._load()
        self.kernel = None

    def _load(self) -> list:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                return []
        return []

    def _save(self):
        self._file.write_text(json.dumps(self.goals, indent=2, default=str))

    async def initialize(self, kernel):
        self.kernel = kernel

    async def shutdown(self):
        self._save()

    def create_goal(self, title: str, description: str = "", deadline: str = None,
                    milestones: list = None, priority: str = "medium") -> dict:
        """Create a new goal."""
        goal = {
            "id": f"goal_{int(datetime.now().timestamp() * 1000)}",
            "title": title,
            "description": description,
            "status": "active",  # active | completed | paused | abandoned
            "priority": priority,  # low | medium | high | critical
            "deadline": deadline,
            "milestones": [],
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "notes": [],
        }
        if milestones:
            for i, m in enumerate(milestones):
                goal["milestones"].append({
                    "id": f"ms_{i}",
                    "title": m if isinstance(m, str) else m.get("title", ""),
                    "completed": False,
                    "completed_at": None,
                })
        self.goals.append(goal)
        self._save()
        logger.info(f"Goal created: {title}")
        return goal

    def update_goal(self, goal_id: str, updates: dict) -> Optional[dict]:
        """Update a goal's properties."""
        for goal in self.goals:
            if goal["id"] == goal_id:
                for key, value in updates.items():
                    if key in ("title", "description", "status", "priority", "deadline", "progress"):
                        goal[key] = value
                goal["updated_at"] = datetime.now().isoformat()
                self._save()
                return goal
        return None

    def complete_milestone(self, goal_id: str, milestone_id: str) -> Optional[dict]:
        """Mark a milestone as completed and recalculate progress."""
        for goal in self.goals:
            if goal["id"] == goal_id:
                for ms in goal["milestones"]:
                    if ms["id"] == milestone_id:
                        ms["completed"] = True
                        ms["completed_at"] = datetime.now().isoformat()
                        break
                # Recalculate progress
                total = len(goal["milestones"])
                done = sum(1 for m in goal["milestones"] if m["completed"])
                goal["progress"] = round(done / total * 100) if total > 0 else 0
                if goal["progress"] == 100:
                    goal["status"] = "completed"
                goal["updated_at"] = datetime.now().isoformat()
                self._save()
                return goal
        return None

    def add_note(self, goal_id: str, note: str) -> Optional[dict]:
        """Add a progress note to a goal."""
        for goal in self.goals:
            if goal["id"] == goal_id:
                goal["notes"].append({
                    "content": note,
                    "timestamp": datetime.now().isoformat(),
                })
                goal["updated_at"] = datetime.now().isoformat()
                self._save()
                return goal
        return None

    def get_active_goals(self) -> list:
        return [g for g in self.goals if g["status"] == "active"]

    def get_all_goals(self) -> list:
        return self.goals

    def get_goal(self, goal_id: str) -> Optional[dict]:
        for goal in self.goals:
            if goal["id"] == goal_id:
                return goal
        return None

    def delete_goal(self, goal_id: str) -> bool:
        before = len(self.goals)
        self.goals = [g for g in self.goals if g["id"] != goal_id]
        if len(self.goals) < before:
            self._save()
            return True
        return False

    def generate_briefing(self) -> str:
        """Generate a morning briefing about active goals."""
        active = self.get_active_goals()
        if not active:
            return "No active goals. Would you like to set some?"

        lines = [f"You have {len(active)} active goal{'s' if len(active) != 1 else ''}:\n"]
        for i, g in enumerate(active, 1):
            status_icon = "🔴" if g["priority"] == "critical" else "🟡" if g["priority"] == "high" else "🟢"
            lines.append(f"{i}. {g['title']} — {g['progress']}% complete")
            if g.get("deadline"):
                try:
                    deadline = datetime.fromisoformat(g["deadline"])
                    days_left = (deadline - datetime.now()).days
                    if days_left < 0:
                        lines.append(f"   OVERDUE by {abs(days_left)} days!")
                    elif days_left <= 3:
                        lines.append(f"   Due in {days_left} day{'s' if days_left != 1 else ''} — urgent!")
                    else:
                        lines.append(f"   Due in {days_left} days")
                except (ValueError, TypeError):
                    pass
            pending_ms = [m for m in g.get("milestones", []) if not m["completed"]]
            if pending_ms:
                lines.append(f"   Next: {pending_ms[0]['title']}")

        return "\n".join(lines)
