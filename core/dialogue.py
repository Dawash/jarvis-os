"""
JARVIS-OS Dialogue State Machine — Multi-turn conversation tracking.
Tracks conversation state to prevent context loss in long exchanges.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.dialogue")


class DialogueState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PLANNING = "planning"
    CONFIRMING = "confirming"
    EXECUTING = "executing"
    REPORTING = "reporting"
    FOLLOW_UP = "follow_up"
    CLARIFYING = "clarifying"
    ERROR = "error"


class DialogueContext:
    """Represents the current dialogue context."""

    def __init__(self):
        self.state = DialogueState.IDLE
        self.topic: str = ""
        self.intent: str = ""
        self.entities: dict = {}
        self.history: list[dict] = []
        self.pending_confirmation: dict = None
        self.follow_up_expected: bool = False
        self.turn_count: int = 0
        self.started_at: str = datetime.now().isoformat()
        self.last_update: str = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "topic": self.topic,
            "intent": self.intent,
            "entities": self.entities,
            "turn_count": self.turn_count,
            "follow_up_expected": self.follow_up_expected,
            "pending_confirmation": self.pending_confirmation,
            "started_at": self.started_at,
            "last_update": self.last_update,
            "history_length": len(self.history),
        }


class DialogueManager:
    """Manages dialogue state across multi-turn conversations."""

    def __init__(self):
        self.active_contexts: dict[str, DialogueContext] = {}
        self.default_context = DialogueContext()
        self.kernel = None

    async def initialize(self, kernel):
        self.kernel = kernel

    async def shutdown(self):
        pass

    def get_context(self, session_id: str = "default") -> DialogueContext:
        if session_id not in self.active_contexts:
            self.active_contexts[session_id] = DialogueContext()
        return self.active_contexts[session_id]

    def transition(self, session_id: str = "default", new_state: DialogueState = None,
                   topic: str = None, intent: str = None, entities: dict = None):
        """Transition dialogue to a new state."""
        ctx = self.get_context(session_id)

        if new_state:
            old_state = ctx.state
            ctx.state = new_state
            logger.debug(f"Dialogue [{session_id}]: {old_state.value} → {new_state.value}")

        if topic:
            ctx.topic = topic
        if intent:
            ctx.intent = intent
        if entities:
            ctx.entities.update(entities)

        ctx.last_update = datetime.now().isoformat()

    def add_turn(self, session_id: str = "default", role: str = "user",
                 content: str = "", metadata: dict = None):
        """Add a conversation turn to the dialogue history."""
        ctx = self.get_context(session_id)
        ctx.history.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "state": ctx.state.value,
            "timestamp": datetime.now().isoformat(),
        })
        ctx.turn_count += 1
        ctx.last_update = datetime.now().isoformat()

        # Keep history bounded
        if len(ctx.history) > 50:
            ctx.history = ctx.history[-50:]

    def set_pending_confirmation(self, session_id: str = "default",
                                  action: str = "", details: dict = None):
        """Set a pending confirmation (e.g., 'Are you sure you want to delete?')."""
        ctx = self.get_context(session_id)
        ctx.pending_confirmation = {
            "action": action,
            "details": details or {},
            "asked_at": datetime.now().isoformat(),
        }
        ctx.state = DialogueState.CONFIRMING

    def resolve_confirmation(self, session_id: str = "default", confirmed: bool = True) -> dict:
        """Resolve a pending confirmation."""
        ctx = self.get_context(session_id)
        if not ctx.pending_confirmation:
            return {"status": "error", "message": "No pending confirmation"}

        result = ctx.pending_confirmation.copy()
        result["confirmed"] = confirmed
        ctx.pending_confirmation = None
        ctx.state = DialogueState.EXECUTING if confirmed else DialogueState.IDLE
        return result

    def is_follow_up(self, session_id: str = "default", message: str = "") -> bool:
        """Determine if a message is a follow-up to the current conversation."""
        ctx = self.get_context(session_id)

        # If context expects follow-up
        if ctx.follow_up_expected:
            return True

        # If we're in certain states, treat as follow-up
        if ctx.state in (DialogueState.CONFIRMING, DialogueState.FOLLOW_UP,
                         DialogueState.CLARIFYING):
            return True

        # Check for referential language
        follow_up_indicators = [
            "also", "and also", "what about", "how about",
            "actually", "wait", "go back", "change that",
            "instead", "never mind", "cancel", "undo",
            "yes", "no", "sure", "okay", "confirm",
            "that's right", "correct", "wrong",
        ]
        msg_lower = message.lower().strip()
        for indicator in follow_up_indicators:
            if msg_lower.startswith(indicator) or msg_lower == indicator:
                return True

        return False

    def get_conversation_summary(self, session_id: str = "default") -> str:
        """Get a summary of the current conversation for context injection."""
        ctx = self.get_context(session_id)
        if not ctx.history:
            return ""

        parts = []
        if ctx.topic:
            parts.append(f"Topic: {ctx.topic}")
        if ctx.intent:
            parts.append(f"Intent: {ctx.intent}")
        parts.append(f"State: {ctx.state.value}")
        parts.append(f"Turns: {ctx.turn_count}")

        # Last few exchanges
        recent = ctx.history[-6:]
        for turn in recent:
            role = turn["role"].upper()
            content = turn["content"][:150]
            parts.append(f"{role}: {content}")

        return "\n".join(parts)

    def reset(self, session_id: str = "default"):
        """Reset dialogue context for a new conversation."""
        if session_id in self.active_contexts:
            del self.active_contexts[session_id]

    def get_all_contexts(self) -> dict:
        return {k: v.to_dict() for k, v in self.active_contexts.items()}
