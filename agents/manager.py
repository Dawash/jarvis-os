"""
JARVIS-OS Agent Manager — Orchestrates agents with planning, dialogue, and all subsystems.
"""

import asyncio
import logging
import re
import time
from datetime import datetime

from agents.agent import Agent, AgentStatus
from agents.planner import TaskPlanner
from agents.llm_provider import LLMProvider

logger = logging.getLogger("jarvis.agents")

# Quick command patterns that bypass LLM
QUICK_COMMANDS = {
    r"^(hi|hello|hey|good morning|good evening)\b": lambda m: f"Hello! I'm JARVIS. How can I assist you today?",
    r"^what time": lambda m: f"The current time is {datetime.now().strftime('%I:%M %p')}.",
    r"^what('?s| is) the date": lambda m: f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.",
    r"^system status$": lambda m: None,  # handled specially
    r"^(clear|cls)$": lambda m: "__clear__",
    r"^undo$": lambda m: "__undo__",
    r"^briefing$": lambda m: "__briefing__",
}


class AgentManager:
    """Manages agent lifecycle with planning, dialogue context, and progress events."""

    def __init__(self, config: dict):
        self.config = config
        self.llm = LLMProvider(config)
        self.planner = TaskPlanner(self.llm)
        self.agents: dict[str, Agent] = {}
        self.max_concurrent = config.get("agents", {}).get("max_concurrent", 10)
        self.kernel = None
        self.plugin_manager = None
        self.action_history = None
        self.goals_manager = None
        self.dialogue_manager = None

    async def initialize(self, kernel):
        self.kernel = kernel
        self.plugin_manager = kernel.subsystems.get("plugins")
        self.action_history = kernel.subsystems.get("action_history")
        self.goals_manager = kernel.subsystems.get("goals")
        self.dialogue_manager = kernel.subsystems.get("dialogue")

        # Connect LLM router
        lr = kernel.subsystems.get("llm_router")
        if lr:
            lr.llm_provider = self.llm

    async def shutdown(self):
        for agent in self.agents.values():
            if agent.status == AgentStatus.RUNNING:
                agent.cancel()

    async def process(self, command: str, source: str = "dashboard") -> dict:
        """Process a command — quick check → dialogue → plan → execute."""
        command = command.strip()
        if not command:
            return {"result": "", "status": "empty"}

        # 1. Quick commands
        quick = self._check_quick_commands(command)
        if quick:
            return quick

        # 2. Update dialogue state
        if self.dialogue_manager:
            ctx = self.dialogue_manager.get_context(source)
            self.dialogue_manager.add_turn(source, "user", command)
            self.dialogue_manager.transition(source, new_state=__import__("core.dialogue", fromlist=["DialogueState"]).DialogueState.PLANNING)

        # 3. Emit planning event
        if self.kernel:
            from core.kernel import Event
            await self.kernel.emit_event(Event("agent.planning", {"command": command}))

        # 4. Create plan
        memory_context = ""
        if self.kernel:
            mem = self.kernel.subsystems.get("memory")
            if mem:
                relevant = mem.query_all_tiers(command)
                if any(relevant.values()):
                    parts = []
                    for tier, items in relevant.items():
                        if items:
                            for item in items[:3]:
                                content = item.get("content", "") or item.get("fact", "")
                                if content:
                                    parts.append(f"[{tier}] {content[:100]}")
                    if parts:
                        memory_context = "Relevant memory:\n" + "\n".join(parts)

        plan = await self.planner.create_plan(command, memory_context)

        # 5. Check for direct response
        if plan.get("direct_response"):
            result = plan["direct_response"]
            if self.dialogue_manager:
                self.dialogue_manager.add_turn(source, "jarvis", result)
                self.dialogue_manager.transition(source, new_state=__import__("core.dialogue", fromlist=["DialogueState"]).DialogueState.IDLE)
            return {"result": result, "status": "completed", "plan": plan}

        # 6. Emit plan
        if self.kernel:
            from core.kernel import Event
            await self.kernel.emit_event(Event("agent.plan_ready", {
                "plan": plan, "steps": plan.get("steps", []),
            }))

        # 7. Spawn agent
        agent = self._spawn_agent(command, plan)

        # 8. Update dialogue state
        if self.dialogue_manager:
            self.dialogue_manager.transition(source, new_state=__import__("core.dialogue", fromlist=["DialogueState"]).DialogueState.EXECUTING)

        # 9. Execute
        async def progress_callback(event_data):
            if self.kernel:
                from core.kernel import Event
                event_data["agent_id"] = agent.agent_id
                await self.kernel.emit_event(Event("agent.step", event_data))

        result = await agent.run(command, callback=progress_callback)

        # 10. Store in memory
        if self.kernel:
            mem = self.kernel.subsystems.get("memory")
            if mem:
                mem.store_conversation("user", command, {"source": source})
                mem.store_conversation("jarvis", result.get("result", ""), {"agent_id": agent.agent_id})
                mem.log_task(command, result.get("result", "")[:500], result.get("status", ""))

        # 11. Emit completion
        if self.kernel:
            from core.kernel import Event
            await self.kernel.emit_event(Event("agent.completed", {
                "agent_id": agent.agent_id,
                "result": result.get("result", ""),
                "status": result.get("status", ""),
                "steps": len(result.get("steps", [])),
            }))

        # 12. Update dialogue
        if self.dialogue_manager:
            self.dialogue_manager.add_turn(source, "jarvis", result.get("result", "")[:500])
            self.dialogue_manager.transition(source, new_state=__import__("core.dialogue", fromlist=["DialogueState"]).DialogueState.IDLE)

        return {
            "result": result.get("result", ""),
            "status": result.get("status", "completed"),
            "agent_id": agent.agent_id,
            "plan": plan,
            "steps": result.get("steps", []),
        }

    def _check_quick_commands(self, command: str) -> dict:
        """Check for quick commands that bypass LLM."""
        cmd_lower = command.lower().strip()

        for pattern, handler in QUICK_COMMANDS.items():
            match = re.match(pattern, cmd_lower)
            if match:
                result = handler(match)

                if result == "__clear__":
                    return {"result": "", "status": "completed", "action": "clear"}

                if result == "__undo__":
                    # Handle async undo
                    return {"result": "Processing undo...", "status": "completed", "action": "undo"}

                if result == "__briefing__":
                    if self.goals_manager:
                        briefing = self.goals_manager.generate_briefing()
                        return {"result": briefing, "status": "completed"}
                    return {"result": "No goals set yet.", "status": "completed"}

                if result is None and "system status" in cmd_lower:
                    info = self._get_system_status()
                    return {"result": info, "status": "completed"}

                if result:
                    return {"result": result, "status": "completed"}

        return None

    def _get_system_status(self) -> str:
        parts = [
            f"JARVIS-OS v{self.config.get('system', {}).get('version', '2.0.0')}",
            f"LLM: {self.llm.provider} ({self.llm.model})",
            f"Agents: {sum(1 for a in self.agents.values() if a.status == AgentStatus.RUNNING)} running",
            f"Plugins: {len(self.plugin_manager.plugins) if self.plugin_manager else 0} loaded",
        ]
        if self.goals_manager:
            active_goals = len(self.goals_manager.get_active_goals())
            parts.append(f"Goals: {active_goals} active")
        if self.llm.is_offline:
            parts.append("Mode: OFFLINE")
        return " | ".join(parts)

    def _spawn_agent(self, task: str, plan: dict = None) -> Agent:
        """Create a new agent with all subsystem connections."""
        agent_id = f"agent_{int(time.time() * 1000)}"
        agent = Agent(
            agent_id=agent_id,
            name=f"Agent-{len(self.agents) + 1}",
            agent_type=plan.get("type", "general") if plan else "general",
            llm_provider=self.llm,
            system_control=self.kernel.subsystems.get("system_control") if self.kernel else None,
            memory=self.kernel.subsystems.get("memory") if self.kernel else None,
            plugin_manager=self.plugin_manager,
            action_history=self.action_history,
            goals_manager=self.goals_manager,
            dialogue_manager=self.dialogue_manager,
        )
        agent.plan = plan
        self.agents[agent_id] = agent
        return agent

    def cancel_agent(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if agent:
            agent.cancel()
