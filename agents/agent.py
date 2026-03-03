"""
JARVIS-OS Agent — Autonomous AI agent with plan-driven execution.
Executes tasks using a Think → Act → Observe loop with self-correction.
Supports streaming progress updates to the dashboard in real-time.
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
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Agent:
    """
    An autonomous AI agent that plans, executes tools, and self-corrects.
    Runs an execution loop: Plan → Think → Act → Observe → Repeat.
    """

    def __init__(
        self,
        agent_id: str = None,
        name: str = "Agent",
        agent_type: str = "general",
        llm_provider=None,
        system_control=None,
        memory=None,
        plugin_manager=None,
        tools: list = None,
    ):
        self.id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.agent_type = agent_type
        self.llm = llm_provider
        self.system_control = system_control
        self.memory = memory
        self.plugin_manager = plugin_manager
        self.status = AgentStatus.IDLE
        self.created_at = datetime.now()

        # Execution state
        self.task = None
        self.plan = None
        self.messages = []
        self.steps = []
        self.result = None
        self.error = None
        self.max_steps = 25
        self.retry_count = 0
        self.max_retries = 2
        self._cancel_flag = False

        # Action history for undo support
        self.action_history = []

        # Tools available to this agent
        self.tools = tools or self._default_tools()

    def _default_tools(self) -> list:
        """Define the tools available to this agent."""
        tools = [
            {
                "name": "execute_shell",
                "description": "Execute a shell command on the system. Use for running programs, scripts, system commands. Returns stdout, stderr, and return code.",
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
                "description": "Read the contents of a file. Returns content, size, and line count.",
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
                "name": "web_search",
                "description": "Search the web for real-time information. Returns titles, URLs, and snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "max_results": {"type": "integer", "description": "Max results (default 5)"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "fetch_url",
                "description": "Fetch and read the content of a web page. Returns extracted text content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to fetch"},
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "run_python",
                "description": "Execute Python code in a sandboxed environment. Use for calculations, data processing, testing code. Returns stdout and any errors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                    },
                    "required": ["code"],
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
                "name": "take_screenshot",
                "description": "Capture a screenshot of the current screen.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "output_path": {"type": "string", "description": "Path to save screenshot (optional)"},
                    },
                },
            },
            {
                "name": "remember",
                "description": "Store a fact or information in long-term memory for future recall.",
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
                "description": "Report that the task is complete with a final result/summary. Call this when you are done.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "result": {"type": "string", "description": "Final result or summary"},
                    },
                    "required": ["result"],
                },
            },
        ]
        return tools

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

        plan_context = ""
        if self.plan:
            completed = [s for s in self.plan.get("steps", []) if s.get("status") == "completed"]
            remaining = [s for s in self.plan.get("steps", []) if s.get("status") != "completed"]
            plan_context = f"""
CURRENT PLAN for goal: {self.plan.get('goal', self.task)}
Completed steps: {len(completed)}/{len(self.plan.get('steps', []))}
Remaining: {json.dumps([{'id': s['id'], 'desc': s['description']} for s in remaining[:5]], indent=2)}

Follow this plan step by step. After completing each step, move to the next.
"""

        return f"""You are {self.name}, an autonomous AI agent within JARVIS-OS.
{type_instructions.get(self.agent_type, type_instructions['general'])}
{plan_context}
RULES:
1. Think step-by-step before acting. Explain your reasoning briefly.
2. Use tools to interact with the system — do not guess or make up information.
3. Execute one tool at a time, observe the result, then decide next action.
4. If a step fails, analyze why and try an alternative approach before giving up.
5. When you have completed the task, call report_complete with a clear summary.
6. Be efficient — minimize unnecessary steps.
7. For multi-step tasks, work through the plan systematically.
8. Never execute dangerous commands (rm -rf /, format, etc.) without explicit user confirmation.
9. When searching the web, use web_search first, then fetch_url on promising results.
10. When writing code, use run_python to test it before delivering.

You have full access to the system through your tools. Use them wisely."""

    async def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call and return the result."""
        try:
            # Record action for history/undo
            self.action_history.append({
                "tool": tool_name,
                "args": arguments,
                "timestamp": datetime.now().isoformat(),
            })

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
            elif tool_name == "take_screenshot":
                result = self.system_control.take_screenshot(**arguments)
            elif tool_name == "remember":
                self.memory.store_fact(**arguments)
                result = {"status": "success", "message": "Stored in memory"}
            elif tool_name == "recall":
                result = self.memory.search_conversations(**arguments)
            elif tool_name == "spawn_agent":
                result = {"status": "spawned", "task": arguments.get("task")}
            elif tool_name == "report_complete":
                self.result = arguments.get("result", "Task completed")
                result = {"status": "complete"}
            # Plugin-provided tools
            elif tool_name in ("web_search", "fetch_url"):
                if self.plugin_manager:
                    result = await self.plugin_manager.execute_plugin_tool(
                        "web_search", tool_name, arguments
                    )
                else:
                    result = {"error": "Web search plugin not available"}
            elif tool_name == "run_python":
                if self.plugin_manager:
                    result = await self.plugin_manager.execute_plugin_tool(
                        "code_runner", tool_name, arguments
                    )
                else:
                    result = {"error": "Code runner plugin not available"}
            else:
                # Try plugin tools
                if self.plugin_manager:
                    for plugin_name, plugin in self.plugin_manager.plugins.items():
                        for t in plugin.tools:
                            if t["name"] == tool_name:
                                result = await self.plugin_manager.execute_plugin_tool(
                                    plugin_name, tool_name, arguments
                                )
                                return json.dumps(result, default=str)
                result = {"error": f"Unknown tool: {tool_name}"}

            return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return json.dumps({"error": str(e)})

    async def run(self, task: str, callback=None) -> dict:
        """
        Main execution loop: Think → Act → Observe → Repeat.
        With plan-driven execution and self-correction on failures.
        """
        self.task = task
        self.status = AgentStatus.RUNNING
        self.steps = []
        self.result = None
        self.error = None

        self.messages = [{"role": "user", "content": task}]

        logger.info(f"Agent {self.id} ({self.name}) starting task: {task[:100]}")

        try:
            consecutive_failures = 0

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
                    "status": "running",
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
                            "status": "running",
                        }

                        # Broadcast that we're about to execute this tool
                        step["current_action"] = f"Running {tc['name']}..."

                        # Execute the tool
                        tool_result = await self.execute_tool(tc["name"], tc["arguments"])
                        action["result"] = tool_result
                        action["status"] = "completed"

                        # Check for errors in tool result
                        try:
                            parsed = json.loads(tool_result)
                            if isinstance(parsed, dict) and "error" in parsed:
                                action["status"] = "error"
                                consecutive_failures += 1
                            else:
                                consecutive_failures = 0
                        except (json.JSONDecodeError, TypeError):
                            consecutive_failures = 0

                        step["actions"].append(action)

                        # Add tool result to conversation
                        self.messages.append({
                            "role": "user",
                            "content": f"[Tool Result for {tc['name']}]: {tool_result}"
                        })

                        # Check if task was reported complete
                        if tc["name"] == "report_complete":
                            step["status"] = "completed"
                            self.status = AgentStatus.COMPLETED
                            self.steps.append(step)
                            if callback:
                                await callback(self, step)
                            return {
                                "status": "completed",
                                "result": self.result,
                                "steps": self.steps,
                                "agent_id": self.id,
                                "plan": self.plan,
                            }

                step["status"] = "completed"
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
                        "plan": self.plan,
                    }

                # Self-correction: if too many consecutive failures, inject guidance
                if consecutive_failures >= 3:
                    self.messages.append({
                        "role": "user",
                        "content": "[System] Multiple tool calls have failed. Please reconsider your approach. Try a different tool or method. If the task cannot be completed, call report_complete with an explanation."
                    })
                    consecutive_failures = 0
                    self.retry_count += 1

                    if self.retry_count > self.max_retries:
                        self.messages.append({
                            "role": "user",
                            "content": "[System] Maximum retries exceeded. Please summarize what you've accomplished so far and call report_complete."
                        })

            # Max steps exceeded
            self.status = AgentStatus.FAILED
            self.error = "Max steps exceeded"
            return {
                "status": "max_steps_exceeded",
                "result": self.result or "Task exceeded maximum steps. Partial progress may have been made.",
                "steps": self.steps,
                "agent_id": self.id,
                "plan": self.plan,
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
            "plan": self.plan,
            "steps_count": len(self.steps),
            "steps": self.steps[-5:],  # Last 5 steps for UI
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }
