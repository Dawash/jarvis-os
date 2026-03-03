"""
JARVIS-OS Agent Manager — Orchestrates agents with plan-driven execution,
command routing, and real-time progress broadcasting.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

from agents.agent import Agent, AgentStatus
from agents.planner import TaskPlanner
from agents.llm_provider import LLMProvider
from core.system_control import SystemControl
from core.memory import MemoryStore

logger = logging.getLogger("jarvis.agent_manager")

# Commands that can be handled instantly without LLM
QUICK_COMMANDS = {
    r"^(hi|hello|hey|good morning|good evening)\b": "greeting",
    r"^(what time|current time|time now)": "time",
    r"^(system status|status|sys stats)$": "system_status",
    r"^(clear|cls)$": "clear",
}


class AgentManager:
    """
    Manages the lifecycle and orchestration of all AI agents.
    Routes tasks through planning → execution → observation.
    """

    def __init__(self, config: dict):
        self.config = config
        self.llm = LLMProvider(config["llm"])
        self.system_control = SystemControl()
        self.memory = MemoryStore(config["system"].get("memory_dir", "./memory"))
        self.planner = TaskPlanner(self.llm)

        self.agents: dict[str, Agent] = {}
        self.max_concurrent = config["agents"]["max_concurrent"]
        self.kernel = None
        self.plugin_manager = None

        # Task queue for overflow
        self._task_queue = asyncio.Queue()
        self._running_count = 0

    async def initialize(self, kernel):
        self.kernel = kernel
        await self.system_control.initialize(kernel)
        # Get plugin manager reference for tool dispatch
        self.plugin_manager = kernel.subsystems.get("plugins")
        logger.info(f"Agent Manager online — max {self.max_concurrent} concurrent agents")

    async def shutdown(self):
        # Cancel all running agents
        for agent in self.agents.values():
            if agent.status == AgentStatus.RUNNING:
                agent.cancel()
        await self.memory.shutdown()

    async def process(self, command: str, source: str = "dashboard") -> dict:
        """
        Process a user command:
        1. Check for quick commands (no LLM needed)
        2. Classify the task
        3. Create a plan
        4. Spawn and run an agent with the plan
        """
        # Store in memory
        self.memory.store_conversation("user", command, {"source": source})

        # Check quick commands first
        quick = self._check_quick_command(command)
        if quick:
            self.memory.store_conversation("assistant", quick["result"])
            return quick

        # Classify the task type
        agent_type = await self._classify_task(command)

        # Retrieve relevant memory context
        context = ""
        try:
            recent = self.memory.get_recent_conversations(limit=10)
            if recent:
                context = "\n".join(
                    f"{c['role']}: {c['content'][:200]}" for c in recent[-6:]
                )
        except Exception:
            pass

        # Create a plan for the task
        await self._emit("agent.planning", {
            "task": command[:200],
            "status": "planning",
            "message": "Creating execution plan...",
        })

        plan = await self.planner.create_plan(command, context)

        # Check if plan says it's a direct response (simple Q&A)
        if (len(plan.get("steps", [])) == 1
                and plan["steps"][0].get("tool") == "direct_response"):
            response = plan["steps"][0]["args"].get("response", "")
            self.memory.store_conversation("assistant", response)
            self.memory.log_task(command, response, "completed", "planner")
            return {
                "status": "completed",
                "result": response,
                "agent_id": "planner",
                "plan": plan,
            }

        # Spawn an agent with the plan
        agent = await self.spawn_agent(
            task=command,
            agent_type=agent_type,
            source=source,
        )
        agent.plan = plan

        # Broadcast the plan to dashboard
        await self._emit("agent.plan_ready", {
            "agent_id": agent.id,
            "plan": plan,
            "task": command[:200],
        })

        # Wait for completion
        result = await self._run_agent(agent)

        # Store result in memory
        self.memory.store_conversation(
            "assistant", result.get("result", ""), {"agent_id": agent.id}
        )
        self.memory.log_task(
            command, result.get("result", ""),
            result.get("status", "unknown"), agent.id
        )

        return result

    def _check_quick_command(self, command: str) -> Optional[dict]:
        """Handle instant commands without LLM."""
        cmd_lower = command.strip().lower()

        for pattern, cmd_type in QUICK_COMMANDS.items():
            if re.match(pattern, cmd_lower):
                if cmd_type == "greeting":
                    return {
                        "status": "completed",
                        "result": "Hello! I'm JARVIS, your AI operating system. How can I assist you today?",
                        "agent_id": "quick",
                    }
                elif cmd_type == "time":
                    now = datetime.now().strftime("%H:%M:%S on %A, %B %d, %Y")
                    return {
                        "status": "completed",
                        "result": f"The current time is {now}.",
                        "agent_id": "quick",
                    }
                elif cmd_type == "system_status":
                    stats = self.system_control.get_system_stats()
                    return {
                        "status": "completed",
                        "result": f"CPU: {stats['cpu']['usage_percent']}% | Memory: {stats['memory']['percent']}% ({stats['memory']['used_gb']}/{stats['memory']['total_gb']} GB) | Disk: {stats['disk']['percent']}% | Active Agents: {self._running_count}",
                        "agent_id": "quick",
                    }
                elif cmd_type == "clear":
                    return {
                        "status": "completed",
                        "result": "[CLEAR]",
                        "agent_id": "quick",
                    }
        return None

    async def _classify_task(self, task: str) -> str:
        """Use LLM to classify what type of agent should handle this task."""
        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": task}],
                system="""Classify this task into exactly one category. Respond with ONLY the category name:
- system: file operations, process management, system monitoring, shell commands
- research: web search, information gathering, fact-checking
- code: programming, debugging, code review, code generation
- creative: writing, content creation, brainstorming
- data: data analysis, visualization, statistics, CSV/JSON processing
- automation: scheduling, workflow automation, scripting
- general: anything that doesn't fit above""",
                max_tokens=20,
            )
            category = response["content"].strip().lower()
            valid = ["system", "research", "code", "creative", "data", "automation", "general"]
            return category if category in valid else "general"
        except Exception:
            return "general"

    async def spawn_agent(
        self,
        task: str,
        agent_type: str = "general",
        name: str = None,
        source: str = "system",
    ) -> Agent:
        """Spawn a new agent for a task."""
        agent = Agent(
            name=name or f"JARVIS-{agent_type.upper()}-{len(self.agents) + 1}",
            agent_type=agent_type,
            llm_provider=self.llm,
            system_control=self.system_control,
            memory=self.memory,
            plugin_manager=self.plugin_manager,
        )
        agent.task = task
        self.agents[agent.id] = agent

        # Notify kernel
        if self.kernel:
            self.kernel.state["active_agents"] = sum(
                1 for a in self.agents.values() if a.status == AgentStatus.RUNNING
            )
            await self._emit("agent.spawned", {
                "agent_id": agent.id,
                "name": agent.name,
                "type": agent_type,
                "task": task[:200],
            })

        logger.info(f"Agent spawned: {agent.name} ({agent.id}) — type: {agent_type}")
        return agent

    async def _run_agent(self, agent: Agent) -> dict:
        """Run an agent and handle the result."""
        self._running_count += 1

        async def on_step(ag, step):
            """Callback for each agent step — broadcast to dashboard."""
            await self._emit("agent.step", {
                "agent_id": ag.id,
                "agent_name": ag.name,
                "step": step,
                "total_steps": len(ag.steps),
                "plan_progress": self._get_plan_progress(ag),
            })

        try:
            result = await agent.run(agent.task, callback=on_step)
        except Exception as e:
            result = {"status": "error", "error": str(e), "agent_id": agent.id}
        finally:
            self._running_count -= 1
            if self.kernel:
                self.kernel.state["active_agents"] = self._running_count
                await self._emit("agent.completed", {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "status": result.get("status"),
                    "result": str(result.get("result", ""))[:500],
                    "steps_taken": len(agent.steps),
                })

        return result

    def _get_plan_progress(self, agent: Agent) -> Optional[dict]:
        """Get plan progress info for the UI."""
        if not agent.plan:
            return None
        steps = agent.plan.get("steps", [])
        completed = sum(1 for s in steps if s.get("status") == "completed")
        return {
            "total": len(steps),
            "completed": completed,
            "percent": int((completed / len(steps)) * 100) if steps else 0,
            "current_step": next(
                (s["description"] for s in steps if s.get("status") == "pending"),
                "Finishing up..."
            ),
        }

    async def _emit(self, event_type: str, data: dict):
        """Emit a kernel event."""
        if self.kernel:
            from core.kernel import Event
            await self.kernel.emit_event(Event(event_type, data))

    async def spawn_parallel_agents(self, tasks: list[dict]) -> list[dict]:
        """Spawn multiple agents in parallel."""
        agents = []
        for t in tasks:
            agent = await self.spawn_agent(
                task=t["task"],
                agent_type=t.get("type", "general"),
                name=t.get("name"),
            )
            agents.append(agent)

        results = await asyncio.gather(
            *[self._run_agent(a) for a in agents],
            return_exceptions=True,
        )

        return [
            r if isinstance(r, dict) else {"status": "error", "error": str(r)}
            for r in results
        ]

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> list[dict]:
        return [a.to_dict() for a in self.agents.values()]

    def get_active_agents(self) -> list[dict]:
        return [
            a.to_dict() for a in self.agents.values()
            if a.status == AgentStatus.RUNNING
        ]

    def cancel_agent(self, agent_id: str) -> bool:
        agent = self.agents.get(agent_id)
        if agent and agent.status == AgentStatus.RUNNING:
            agent.cancel()
            return True
        return False
