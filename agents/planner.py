"""
JARVIS-OS Task Planner — Breaks complex goals into executable step-by-step plans.
Inspired by ChatGPT's agentic mode: plan, execute, observe, adapt.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("jarvis.planner")

PLANNER_SYSTEM_PROMPT = """You are a task planning engine inside JARVIS-OS.
Given a user's goal, break it into a concrete plan of sequential steps.

Each step must be a specific, actionable operation using available tools.

Available tools:
- execute_shell: Run shell commands
- read_file / write_file / list_directory / search_files: File operations
- web_search: Search the internet for information
- fetch_url: Fetch and read a web page
- run_python: Execute Python code in a sandbox
- get_system_stats / get_processes / kill_process: System monitoring
- open_application: Launch an application
- remember / recall: Store/retrieve from long-term memory
- take_screenshot: Capture the screen

Respond with ONLY valid JSON — no markdown, no explanation:
{
  "goal": "the user's goal restated clearly",
  "steps": [
    {
      "id": 1,
      "description": "What this step does",
      "tool": "tool_name",
      "args": {"arg1": "value1"},
      "depends_on": [],
      "can_fail": false
    }
  ],
  "estimated_steps": 5
}

Rules:
- Keep plans concise (3-15 steps).
- Mark steps that can fail gracefully with "can_fail": true.
- Use "depends_on" to reference step IDs that must complete first.
- For simple queries (greetings, questions), return a single step using NO tools — just set tool to "direct_response" with args {"response": "your answer"}.
- For research tasks, combine web_search + fetch_url steps.
- For coding tasks, use write_file + run_python to verify.
"""


class TaskPlanner:
    """Decomposes user goals into executable step plans using LLM."""

    def __init__(self, llm_provider):
        self.llm = llm_provider

    async def create_plan(self, goal: str, context: str = "") -> dict:
        """Generate a step-by-step plan for a goal."""
        messages = [{"role": "user", "content": goal}]
        if context:
            messages[0]["content"] = f"Context from memory:\n{context}\n\nGoal: {goal}"

        try:
            response = await self.llm.chat(
                messages=messages,
                system=PLANNER_SYSTEM_PROMPT,
                max_tokens=2048,
                temperature=0.3,
            )

            text = response["content"].strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            plan = json.loads(text)

            # Validate plan structure
            if "steps" not in plan or not isinstance(plan["steps"], list):
                return self._simple_plan(goal)

            # Ensure each step has required fields
            for step in plan["steps"]:
                step.setdefault("id", plan["steps"].index(step) + 1)
                step.setdefault("depends_on", [])
                step.setdefault("can_fail", False)
                step.setdefault("status", "pending")
                step.setdefault("result", None)

            plan.setdefault("goal", goal)
            plan.setdefault("estimated_steps", len(plan["steps"]))

            logger.info(f"Plan created: {len(plan['steps'])} steps for: {goal[:80]}")
            return plan

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Plan parsing failed ({e}), using simple plan")
            return self._simple_plan(goal)
        except Exception as e:
            logger.error(f"Planning error: {e}")
            return self._simple_plan(goal)

    def _simple_plan(self, goal: str) -> dict:
        """Fallback: wrap the goal as a single-step agent task."""
        return {
            "goal": goal,
            "steps": [
                {
                    "id": 1,
                    "description": "Process the request using autonomous reasoning",
                    "tool": "autonomous",
                    "args": {"task": goal},
                    "depends_on": [],
                    "can_fail": False,
                    "status": "pending",
                    "result": None,
                }
            ],
            "estimated_steps": 1,
        }

    async def replan_on_failure(self, original_plan: dict, failed_step: dict, error: str) -> Optional[dict]:
        """Generate an alternative plan when a step fails."""
        messages = [{
            "role": "user",
            "content": f"""The original plan for "{original_plan['goal']}" failed at step {failed_step['id']}: {failed_step['description']}
Error: {error}

Completed steps so far:
{json.dumps([s for s in original_plan['steps'] if s.get('status') == 'completed'], indent=2)}

Create an alternative plan to achieve the same goal, working around this failure.
Start step IDs from {failed_step['id']}.""",
        }]

        try:
            response = await self.llm.chat(
                messages=messages,
                system=PLANNER_SYSTEM_PROMPT,
                max_tokens=2048,
                temperature=0.4,
            )

            text = response["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            new_plan = json.loads(text)
            if "steps" in new_plan:
                for step in new_plan["steps"]:
                    step.setdefault("status", "pending")
                    step.setdefault("result", None)
                logger.info(f"Replanned with {len(new_plan['steps'])} alternative steps")
                return new_plan
        except Exception as e:
            logger.error(f"Replanning failed: {e}")

        return None
