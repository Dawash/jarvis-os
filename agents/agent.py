"""
JARVIS-OS Agent — Individual AI agent that can use tools and complete tasks.
Each agent has a specialization, tools, and autonomous execution loop.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger("jarvis.agent")


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Agent:
    """
    An autonomous AI agent that can reason, use tools, and complete tasks.
    Runs an execution loop: Think -> Act -> Observe -> Repeat.
    """

    def __init__(
        self,
        agent_id: str = None,
        name: str = "Agent",
        agent_type: str = "general",
        llm_provider=None,
        system_control=None,
        memory=None,
        tools: list = None,
    ):
        self.id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.agent_type = agent_type
        self.llm = llm_provider
        self.system_control = system_control
        self.memory = memory
        self.status = AgentStatus.IDLE
        self.created_at = datetime.now()

        # Execution state
        self.task = None
        self.messages = []
        self.steps = []
        self.result = None
        self.error = None
        self.max_steps = 20
        self._cancel_flag = False

        # Tools available to this agent
        self.tools = tools or self._default_tools()

    def _default_tools(self) -> list:
        """Define the tools available to this agent."""
        return [
            {
                "name": "execute_shell",
                "description": "Execute a shell command on the system. Use for running programs, scripts, system commands.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to execute"},
                        "cwd": {"type": "string", "description": "Working directory (optional)"},
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "read_file",
                "description": "Read the contents of a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write content to a file. Creates parent directories if needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file"},
                        "content": {"type": "string", "description": "Content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_directory",
                "description": "List files and directories in a path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "search_files",
                "description": "Search for files matching a pattern.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Directory to search in"},
                        "pattern": {"type": "string", "description": "Glob pattern (e.g. *.py)"},
                    },
                    "required": ["directory", "pattern"],
                },
            },
            {
                "name": "get_system_stats",
                "description": "Get current system statistics (CPU, memory, disk, network).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_processes",
                "description": "List running processes sorted by resource usage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sort_by": {"type": "string", "description": "Sort by: cpu_percent or memory_percent"},
                        "limit": {"type": "integer", "description": "Number of processes to return"},
                    },
                },
            },
            {
                "name": "kill_process",
                "description": "Terminate a process by PID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pid": {"type": "integer", "description": "Process ID to terminate"},
                        "force": {"type": "boolean", "description": "Force kill (SIGKILL)"},
                    },
                    "required": ["pid"],
                },
            },
            {
                "name": "open_application",
                "description": "Open an application by name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Application name or command"},
                    },
                    "required": ["app_name"],
                },
            },
            {
                "name": "remember",
                "description": "Store a fact or information in long-term memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fact": {"type": "string", "description": "The fact or information to remember"},
                        "category": {"type": "string", "description": "Category: general, user, system, task"},
                    },
                    "required": ["fact"],
                },
            },
            {
                "name": "recall",
                "description": "Search long-term memory for relevant information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What to search for"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "spawn_agent",
                "description": "Spawn a sub-agent to handle a specific sub-task in parallel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "The task for the sub-agent"},
                        "agent_type": {"type": "string", "description": "Type: system, research, code, creative, data, automation"},
                    },
                    "required": ["task"],
                },
            },
            {
                "name": "report_complete",
                "description": "Report that the task is complete with a final result/summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "result": {"type": "string", "description": "Final result or summary"},
                    },
                    "required": ["result"],
                },
            },
        ]

    def _get_system_prompt(self) -> str:
        type_instructions = {
            "system": "You are a system operations specialist. You excel at file management, process control, system monitoring, and shell operations.",
            "research": "You are a research specialist. You excel at gathering information, searching the web, analyzing data, and summarizing findings.",
            "code": "You are a coding specialist. You excel at writing, analyzing, debugging, and optimizing code across all programming languages.",
            "creative": "You are a creative specialist. You excel at content creation, writing, brainstorming, and creative problem-solving.",
            "data": "You are a data specialist. You excel at data analysis, visualization, processing datasets, and statistical analysis.",
            "automation": "You are an automation specialist. You excel at creating scripts, scheduling tasks, and automating workflows.",
            "general": "You are a versatile AI agent capable of handling any task.",
        }

        return f"""You are {self.name}, an autonomous AI agent within JARVIS-OS.
{type_instructions.get(self.agent_type, type_instructions['general'])}

RULES:
1. Think step-by-step before acting.
2. Use tools to interact with the system — do not guess or make up information.
3. If you need to do multiple independent things, spawn sub-agents.
4. When you have completed the task, call report_complete with your result.
5. Be efficient — minimize unnecessary steps.
6. If a step fails, analyze why and try an alternative approach.
7. Never execute dangerous commands (rm -rf /, format, etc.) without explicit user confirmation.

You have full access to the system through your tools. Use them wisely."""

    async def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call and return the result."""
        try:
            if tool_name == "execute_shell":
                result = await self.system_control.execute_command(**arguments)
            elif tool_name == "read_file":
                result = self.system_control.read_file(**arguments)
            elif tool_name == "write_file":
                result = self.system_control.write_file(**arguments)
            elif tool_name == "list_directory":
                result = self.system_control.list_directory(**arguments)
            elif tool_name == "search_files":
                result = self.system_control.search_files(**arguments)
            elif tool_name == "get_system_stats":
                result = self.system_control.get_system_stats()
            elif tool_name == "get_processes":
                result = self.system_control.get_processes(**arguments)
            elif tool_name == "kill_process":
                result = self.system_control.kill_process(**arguments)
            elif tool_name == "open_application":
                result = await self.system_control.open_application(**arguments)
            elif tool_name == "remember":
                self.memory.store_fact(**arguments)
                result = {"status": "success", "message": "Stored in memory"}
            elif tool_name == "recall":
                result = self.memory.search_conversations(**arguments)
            elif tool_name == "spawn_agent":
                # This will be handled by the agent manager
                result = {"status": "spawned", "task": arguments.get("task")}
            elif tool_name == "report_complete":
                self.result = arguments.get("result", "Task completed")
                result = {"status": "complete"}
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return json.dumps({"error": str(e)})

    async def run(self, task: str, callback=None) -> dict:
        """
        Main execution loop: Think -> Act -> Observe -> Repeat.
        """
        self.task = task
        self.status = AgentStatus.RUNNING
        self.steps = []
        self.result = None
        self.error = None

        self.messages = [{"role": "user", "content": task}]

        logger.info(f"Agent {self.id} ({self.name}) starting task: {task[:100]}")

        try:
            for step_num in range(self.max_steps):
                if self._cancel_flag:
                    self.status = AgentStatus.CANCELLED
                    return {"status": "cancelled", "steps": self.steps}

                # Think — call the LLM
                response = await self.llm.chat(
                    messages=self.messages,
                    system=self._get_system_prompt(),
                    tools=self.tools,
                )

                step = {
                    "step": step_num + 1,
                    "thought": response["content"],
                    "actions": [],
                    "timestamp": datetime.now().isoformat(),
                }

                # If there's text content, add it as assistant message
                if response["content"]:
                    self.messages.append({"role": "assistant", "content": response["content"]})

                # Act — execute tool calls
                if response["tool_calls"]:
                    for tc in response["tool_calls"]:
                        action = {
                            "tool": tc["name"],
                            "arguments": tc["arguments"],
                        }

                        # Execute the tool
                        tool_result = await self.execute_tool(tc["name"], tc["arguments"])
                        action["result"] = tool_result

                        step["actions"].append(action)

                        # Add tool result to conversation
                        self.messages.append({
                            "role": "user",
                            "content": f"[Tool Result for {tc['name']}]: {tool_result}"
                        })

                        # Check if task was reported complete
                        if tc["name"] == "report_complete":
                            self.status = AgentStatus.COMPLETED
                            self.steps.append(step)
                            if callback:
                                await callback(self, step)
                            return {
                                "status": "completed",
                                "result": self.result,
                                "steps": self.steps,
                                "agent_id": self.id,
                            }

                self.steps.append(step)
                if callback:
                    await callback(self, step)

                # If no tool calls and no more actions, we're done
                if not response["tool_calls"]:
                    self.status = AgentStatus.COMPLETED
                    self.result = response["content"]
                    return {
                        "status": "completed",
                        "result": self.result,
                        "steps": self.steps,
                        "agent_id": self.id,
                    }

            # Max steps exceeded
            self.status = AgentStatus.FAILED
            self.error = "Max steps exceeded"
            return {
                "status": "max_steps_exceeded",
                "result": self.result,
                "steps": self.steps,
                "agent_id": self.id,
            }

        except Exception as e:
            self.status = AgentStatus.FAILED
            self.error = str(e)
            logger.error(f"Agent {self.id} error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "steps": self.steps,
                "agent_id": self.id,
            }

    def cancel(self):
        self._cancel_flag = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.agent_type,
            "status": self.status.value,
            "task": self.task,
            "steps_count": len(self.steps),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }
