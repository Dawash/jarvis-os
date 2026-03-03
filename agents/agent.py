"""
JARVIS-OS Agent — Autonomous AI agent with plan-driven execution.
Think → Act → Observe loop with self-correction and 20+ tools.
"""

import asyncio
import json
import logging
import time
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger("jarvis.agent")


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Agent:
    """Autonomous AI agent with plan-driven execution and self-correction."""

    def __init__(self, agent_id: str, name: str, agent_type: str,
                 llm_provider, system_control=None, memory=None,
                 plugin_manager=None, action_history=None,
                 goals_manager=None, dialogue_manager=None):
        self.agent_id = agent_id
        self.name = name
        self.agent_type = agent_type
        self.llm = llm_provider
        self.system_control = system_control
        self.memory = memory
        self.plugin_manager = plugin_manager
        self.action_history = action_history
        self.goals_manager = goals_manager
        self.dialogue_manager = dialogue_manager

        self.status = AgentStatus.IDLE
        self.task = ""
        self.plan = None
        self.result = None
        self.steps_taken = []
        self.action_history_log = []  # Local action log for this run
        self.retry_count = 0
        self.max_retries = 2
        self.max_steps = 25
        self.created_at = time.time()

    def _get_system_prompt(self) -> str:
        return f"""You are JARVIS, an AI assistant operating as an autonomous agent.
Agent ID: {self.agent_id} | Type: {self.agent_type}
You have access to tools for file operations, shell commands, web search, code execution,
screenshots, reminders, contacts, goals, and memory.
Think step-by-step. If a tool call fails, try an alternative approach.
When the task is complete, call the 'done' tool with a summary."""

    def _get_tools(self) -> list:
        tools = [
            {"name": "read_file", "description": "Read a file's contents",
             "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "write_file", "description": "Write content to a file",
             "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "list_directory", "description": "List files in a directory",
             "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "run_shell", "description": "Execute a shell command",
             "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "web_search", "description": "Search the web",
             "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "fetch_url", "description": "Fetch a web page and extract text",
             "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
            {"name": "run_python", "description": "Execute Python code",
             "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
            {"name": "take_screenshot", "description": "Take a screenshot and analyze it with AI vision",
             "parameters": {"type": "object", "properties": {"question": {"type": "string"}}}},
            {"name": "analyze_image", "description": "Analyze an image with AI vision",
             "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "question": {"type": "string"}}, "required": ["path"]}},
            {"name": "remember", "description": "Store a fact in long-term memory",
             "parameters": {"type": "object", "properties": {"fact": {"type": "string"}, "category": {"type": "string"}}, "required": ["fact"]}},
            {"name": "recall", "description": "Search memory for relevant information",
             "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "set_reminder", "description": "Set a reminder",
             "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "time": {"type": "string"}}, "required": ["message", "time"]}},
            {"name": "search_contacts", "description": "Search contacts",
             "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "add_contact", "description": "Add a new contact",
             "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "relationship": {"type": "string"}, "notes": {"type": "string"}}, "required": ["name"]}},
            {"name": "create_goal", "description": "Create a new goal with milestones",
             "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "milestones": {"type": "array", "items": {"type": "string"}}}, "required": ["title"]}},
            {"name": "get_goals", "description": "Get active goals and briefing",
             "parameters": {"type": "object", "properties": {}}},
            {"name": "undo", "description": "Undo the last reversible action",
             "parameters": {"type": "object", "properties": {}}},
            {"name": "done", "description": "Mark the task as complete with a summary",
             "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
        ]
        return tools

    async def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return the result as a string."""
        try:
            result = await self._dispatch_tool(tool_name, arguments)
            result_str = json.dumps(result, default=str) if isinstance(result, (dict, list)) else str(result)

            # Record in action history
            reversible = tool_name in ("write_file", "run_shell")
            undo_action = None
            if self.action_history and reversible:
                if tool_name == "write_file":
                    path = arguments.get("path", "")
                    from pathlib import Path as P
                    original = None
                    if P(path).exists():
                        try:
                            original = P(path).read_text()
                        except Exception:
                            pass
                    from core.action_history import ActionHistory as AH
                    undo_action = AH.make_file_write_undo(path, original)

                self.action_history.record(
                    tool=tool_name, args=arguments, result=result_str[:300],
                    reversible=reversible, undo_action=undo_action,
                    agent_id=self.agent_id,
                )

            self.action_history_log.append({
                "tool": tool_name, "args": arguments,
                "result": result_str[:500], "timestamp": time.time(),
            })

            return result_str[:3000]

        except Exception as e:
            error_msg = f"Tool error ({tool_name}): {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def _dispatch_tool(self, tool_name: str, arguments: dict):
        """Route tool calls to the appropriate subsystem."""
        # File operations
        if tool_name == "read_file" and self.system_control:
            return self.system_control.read_file(arguments.get("path", ""))
        elif tool_name == "write_file" and self.system_control:
            return self.system_control.write_file(arguments.get("path", ""), arguments.get("content", ""))
        elif tool_name == "list_directory" and self.system_control:
            return self.system_control.list_directory(arguments.get("path", "."))
        elif tool_name == "run_shell" and self.system_control:
            return await self.system_control.execute_command(arguments.get("command", ""))

        # Memory
        elif tool_name == "remember" and self.memory:
            self.memory.store_fact(arguments.get("fact", ""), arguments.get("category", "general"))
            return {"status": "stored"}
        elif tool_name == "recall" and self.memory:
            return self.memory.query_all_tiers(arguments.get("query", ""))

        # Plugin-based tools
        elif tool_name in ("web_search", "fetch_url") and self.plugin_manager:
            return await self.plugin_manager.execute_tool("web_search", tool_name, arguments)
        elif tool_name == "run_python" and self.plugin_manager:
            return await self.plugin_manager.execute_tool("code_runner", tool_name, arguments)
        elif tool_name in ("take_screenshot", "analyze_image") and self.plugin_manager:
            return await self.plugin_manager.execute_tool("screenshot_ocr", tool_name, arguments)

        # Reminders
        elif tool_name == "set_reminder" and self.plugin_manager:
            return await self.plugin_manager.execute_tool("reminders", "set_reminder", arguments)

        # Contacts
        elif tool_name in ("search_contacts", "add_contact") and self.plugin_manager:
            return await self.plugin_manager.execute_tool("contacts", tool_name, arguments)

        # Goals
        elif tool_name == "create_goal" and self.goals_manager:
            return self.goals_manager.create_goal(
                arguments.get("title", ""), arguments.get("description", ""),
                milestones=arguments.get("milestones"),
            )
        elif tool_name == "get_goals" and self.goals_manager:
            return {"briefing": self.goals_manager.generate_briefing(),
                    "goals": self.goals_manager.get_active_goals()}

        # Undo
        elif tool_name == "undo" and self.action_history:
            return await self.action_history.undo_last()

        # Done
        elif tool_name == "done":
            return {"status": "done", "summary": arguments.get("summary", "")}

        return {"error": f"Tool not available: {tool_name}"}

    async def run(self, task: str, callback: Callable = None) -> dict:
        """Execute a task using the Think → Act → Observe loop."""
        self.task = task
        self.status = AgentStatus.RUNNING

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": task},
        ]

        # Add plan context if available
        if self.plan:
            plan_text = "Plan:\n"
            for step in self.plan.get("steps", []):
                plan_text += f"  {step['id']}. {step['description']}\n"
            messages.append({"role": "system", "content": f"Follow this plan:\n{plan_text}"})

        tools = self._get_tools()
        consecutive_failures = 0

        for step_num in range(self.max_steps):
            if self.status == AgentStatus.CANCELLED:
                return {"status": "cancelled", "steps": self.steps_taken}

            try:
                # Think — call LLM
                response = await self.llm.chat(messages, tools=tools)

                if "error" in response:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        messages.append({"role": "system",
                                         "content": "Multiple failures detected. Try a different approach or call 'done' to summarize progress."})
                    if consecutive_failures >= 5:
                        break
                    continue

                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])

                if content and not tool_calls:
                    # No tool calls — check if done
                    messages.append({"role": "assistant", "content": content})
                    self.steps_taken.append({"step": step_num + 1, "type": "think", "content": content[:500]})
                    if callback:
                        await callback({"type": "step", "step": step_num + 1, "content": content[:200]})
                    # If no tool calls after content, we're done
                    self.status = AgentStatus.COMPLETED
                    self.result = content
                    return {"status": "completed", "result": content, "steps": self.steps_taken}

                if not tool_calls:
                    consecutive_failures += 1
                    continue

                # Act — execute tool calls
                consecutive_failures = 0
                assistant_msg = {"role": "assistant", "content": content or ""}
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                for tc in tool_calls:
                    tool_name = tc["name"]
                    try:
                        args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                    except json.JSONDecodeError:
                        args = {}

                    # Done signal
                    if tool_name == "done":
                        summary = args.get("summary", content or "Task completed")
                        self.status = AgentStatus.COMPLETED
                        self.result = summary
                        self.steps_taken.append({"step": step_num + 1, "type": "done", "summary": summary})
                        if callback:
                            await callback({"type": "done", "summary": summary})
                        return {"status": "completed", "result": summary, "steps": self.steps_taken}

                    # Execute tool
                    result = await self.execute_tool(tool_name, args)

                    self.steps_taken.append({
                        "step": step_num + 1, "type": "tool",
                        "tool": tool_name, "args": args,
                        "result": result[:300],
                    })

                    if callback:
                        await callback({
                            "type": "tool", "step": step_num + 1,
                            "tool": tool_name, "result": result[:200],
                        })

                    # Observe — feed result back to LLM
                    messages.append({
                        "role": "tool" if self.llm.provider == "openai" else "user",
                        "content": f"[Tool result: {tool_name}]\n{result}",
                        **({"tool_call_id": tc.get("id", "")} if self.llm.provider == "openai" else {}),
                    })

            except Exception as e:
                logger.error(f"Agent step error: {e}")
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    break

        # Max steps reached
        self.status = AgentStatus.COMPLETED
        summary = self.result or f"Completed after {len(self.steps_taken)} steps."
        return {"status": "completed", "result": summary, "steps": self.steps_taken}

    def cancel(self):
        self.status = AgentStatus.CANCELLED
