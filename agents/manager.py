"""
JARVIS-OS Agent Manager — Orchestrates multiple agents, handles spawning,
task routing, and concurrent execution.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from agents.agent import Agent, AgentStatus
from agents.llm_provider import LLMProvider
from core.system_control import SystemControl
from core.memory import MemoryStore

logger = logging.getLogger("jarvis.agent_manager")


class AgentManager:
    """
    Manages the lifecycle and orchestration of all AI agents.
    Routes tasks, spawns agents, and tracks execution.
    """

    def __init__(self, config: dict):
        self.config = config
        self.llm = LLMProvider(config["llm"])
        self.system_control = SystemControl()
        self.memory = MemoryStore(config["system"].get("memory_dir", "./memory"))

        self.agents: dict[str, Agent] = {}
        self.max_concurrent = config["agents"]["max_concurrent"]
        self.kernel = None

        # Task queue for overflow
        self._task_queue = asyncio.Queue()
        self._running_count = 0

    async def initialize(self, kernel):
        self.kernel = kernel
        await self.system_control.initialize(kernel)
        logger.info(f"Agent Manager online — max {self.max_concurrent} concurrent agents")

    async def shutdown(self):
        # Cancel all running agents
        for agent in self.agents.values():
            if agent.status == AgentStatus.RUNNING:
                agent.cancel()
        await self.memory.shutdown()

    async def process(self, command: str, source: str = "dashboard") -> dict:
        """
        Process a user command — classify, route, and execute.
        """
        # Store in memory
        self.memory.store_conversation("user", command, {"source": source})

        # Create an agent for this task
        agent = await self.spawn_agent(
            task=command,
            agent_type=await self._classify_task(command),
            source=source,
        )

        # Wait for completion
        result = await self._run_agent(agent)

        # Store result in memory
        self.memory.store_conversation("assistant", result.get("result", ""), {"agent_id": agent.id})
        self.memory.log_task(command, result.get("result", ""), result.get("status", "unknown"), agent.id)

        return result

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
        )
        agent.task = task
        self.agents[agent.id] = agent

        # Notify kernel
        if self.kernel:
            self.kernel.state["active_agents"] = sum(
                1 for a in self.agents.values() if a.status == AgentStatus.RUNNING
            )
            from core.kernel import Event
            await self.kernel.emit_event(Event("agent.spawned", {
                "agent_id": agent.id,
                "name": agent.name,
                "type": agent_type,
                "task": task[:200],
            }))

        logger.info(f"Agent spawned: {agent.name} ({agent.id}) — type: {agent_type}")
        return agent

    async def _run_agent(self, agent: Agent) -> dict:
        """Run an agent and handle the result."""
        self._running_count += 1

        async def on_step(ag, step):
            """Callback for each agent step — broadcast to dashboard."""
            if self.kernel:
                from core.kernel import Event
                await self.kernel.emit_event(Event("agent.step", {
                    "agent_id": ag.id,
                    "agent_name": ag.name,
                    "step": step,
                }))

        try:
            result = await agent.run(agent.task, callback=on_step)
        except Exception as e:
            result = {"status": "error", "error": str(e), "agent_id": agent.id}
        finally:
            self._running_count -= 1
            if self.kernel:
                self.kernel.state["active_agents"] = self._running_count
                from core.kernel import Event
                await self.kernel.emit_event(Event("agent.completed", {
                    "agent_id": agent.id,
                    "status": result.get("status"),
                    "result": str(result.get("result", ""))[:500],
                }))

        return result

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
