"""
JARVIS-OS API Routes — REST endpoints for all subsystems.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("jarvis.api")
router = APIRouter()


def get_kernel(request: Request):
    from main import kernel
    return kernel


# ── System ───────────────────────────────────────────────────────

@router.get("/system/info")
async def system_info(request: Request):
    kernel = get_kernel(request)
    return {
        "name": kernel.config.get("system", {}).get("name", "JARVIS-OS"),
        "version": kernel.config.get("system", {}).get("version", "1.0.0"),
        "codename": kernel.config.get("system", {}).get("codename", "ARC REACTOR"),
        "status": kernel.state,
        "subsystems": list(kernel.subsystems.keys()),
    }

@router.get("/system/stats")
async def system_stats(request: Request):
    kernel = get_kernel(request)
    sc = kernel.subsystems.get("system_control")
    if sc:
        return sc.get_system_stats()
    return {"error": "System control not available"}

@router.get("/system/processes")
async def system_processes(request: Request, limit: int = 15):
    kernel = get_kernel(request)
    sc = kernel.subsystems.get("system_control")
    if sc:
        return sc.get_processes(limit)
    return []


# ── Commands ─────────────────────────────────────────────────────

class CommandRequest(BaseModel):
    command: str
    source: str = "api"

@router.post("/command")
async def run_command(req: CommandRequest, request: Request):
    kernel = get_kernel(request)
    result = await kernel.process_command(req.command, req.source)
    return result


# ── Execute Shell ────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    command: str

@router.post("/execute")
async def execute_shell(req: ExecuteRequest, request: Request):
    kernel = get_kernel(request)
    sc = kernel.subsystems.get("system_control")
    if sc:
        return await sc.execute_command(req.command)
    return {"error": "System control not available"}


# ── Files ────────────────────────────────────────────────────────

@router.get("/files/list")
async def list_files(request: Request, path: str = "."):
    kernel = get_kernel(request)
    sc = kernel.subsystems.get("system_control")
    if sc:
        return sc.list_directory(path)
    return {"error": "System control not available"}


# ── Agents ───────────────────────────────────────────────────────

@router.get("/agents")
async def list_agents(request: Request):
    kernel = get_kernel(request)
    am = kernel.subsystems.get("agents")
    if am:
        return [
            {"id": a.agent_id, "name": a.name, "task": a.task,
             "status": a.status.value, "agent_type": a.agent_type}
            for a in am.agents.values()
        ]
    return []

class SpawnRequest(BaseModel):
    task: str
    type: str = "general"

@router.post("/agents/spawn")
async def spawn_agent(req: SpawnRequest, request: Request):
    kernel = get_kernel(request)
    am = kernel.subsystems.get("agents")
    if am:
        result = await am.process(req.task, "api")
        return result
    return {"error": "Agent manager not available"}


# ── Memory ───────────────────────────────────────────────────────

@router.get("/memory/conversations")
async def get_conversations(request: Request, limit: int = 50):
    kernel = get_kernel(request)
    mem = kernel.subsystems.get("memory")
    return mem.get_recent_conversations(limit) if mem else []

@router.get("/memory/facts")
async def get_facts(request: Request, category: str = None):
    kernel = get_kernel(request)
    mem = kernel.subsystems.get("memory")
    return mem.get_facts(category) if mem else []

@router.get("/memory/tasks")
async def get_tasks(request: Request, limit: int = 50):
    kernel = get_kernel(request)
    mem = kernel.subsystems.get("memory")
    return mem.get_task_history(limit) if mem else []

@router.get("/memory/stats")
async def memory_stats(request: Request):
    kernel = get_kernel(request)
    mem = kernel.subsystems.get("memory")
    return mem.get_memory_stats() if mem else {}

@router.get("/memory/search")
async def search_memory(request: Request, q: str = ""):
    kernel = get_kernel(request)
    mem = kernel.subsystems.get("memory")
    if mem and q:
        return mem.query_all_tiers(q)
    return {"stm": [], "mtm": [], "lpm": [], "conversations": []}

@router.get("/memory/profile")
async def user_profile(request: Request):
    kernel = get_kernel(request)
    mem = kernel.subsystems.get("memory")
    return mem.get_user_profile() if mem else {}

@router.get("/memory/hot")
async def hot_memories(request: Request, limit: int = 10):
    kernel = get_kernel(request)
    mem = kernel.subsystems.get("memory")
    return mem.mtm_get_hot(limit) if mem else []


# ── Action History & Undo ────────────────────────────────────────

@router.get("/actions")
async def action_history(request: Request, limit: int = 50):
    kernel = get_kernel(request)
    ah = kernel.subsystems.get("action_history")
    return ah.get_history(limit) if ah else []

@router.get("/actions/reversible")
async def reversible_actions(request: Request, limit: int = 20):
    kernel = get_kernel(request)
    ah = kernel.subsystems.get("action_history")
    return ah.get_reversible_actions(limit) if ah else []

@router.post("/actions/undo")
async def undo_action(request: Request):
    kernel = get_kernel(request)
    ah = kernel.subsystems.get("action_history")
    if ah:
        return await ah.undo_last()
    return {"status": "error", "message": "Action history not available"}


# ── Goals ────────────────────────────────────────────────────────

@router.get("/goals")
async def list_goals(request: Request):
    kernel = get_kernel(request)
    gm = kernel.subsystems.get("goals")
    return gm.get_all_goals() if gm else []

@router.get("/goals/active")
async def active_goals(request: Request):
    kernel = get_kernel(request)
    gm = kernel.subsystems.get("goals")
    return gm.get_active_goals() if gm else []

@router.get("/goals/briefing")
async def goal_briefing(request: Request):
    kernel = get_kernel(request)
    gm = kernel.subsystems.get("goals")
    return {"briefing": gm.generate_briefing()} if gm else {"briefing": "Goals not available"}

class CreateGoalRequest(BaseModel):
    title: str
    description: str = ""
    deadline: str = None
    milestones: list = None
    priority: str = "medium"

@router.post("/goals")
async def create_goal(req: CreateGoalRequest, request: Request):
    kernel = get_kernel(request)
    gm = kernel.subsystems.get("goals")
    if gm:
        return gm.create_goal(req.title, req.description, req.deadline, req.milestones, req.priority)
    return {"error": "Goals not available"}

class UpdateGoalRequest(BaseModel):
    updates: dict = {}

@router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, req: UpdateGoalRequest, request: Request):
    kernel = get_kernel(request)
    gm = kernel.subsystems.get("goals")
    if gm:
        result = gm.update_goal(goal_id, req.updates)
        return result or {"error": "Goal not found"}
    return {"error": "Goals not available"}

@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, request: Request):
    kernel = get_kernel(request)
    gm = kernel.subsystems.get("goals")
    if gm:
        return {"deleted": gm.delete_goal(goal_id)}
    return {"error": "Goals not available"}


# ── LLM Router / Token Budget ───────────────────────────────────

@router.get("/llm/stats")
async def llm_stats(request: Request):
    kernel = get_kernel(request)
    lr = kernel.subsystems.get("llm_router")
    return lr.get_stats() if lr else {}

@router.get("/llm/budget")
async def llm_budget(request: Request):
    kernel = get_kernel(request)
    lr = kernel.subsystems.get("llm_router")
    return lr.get_budget_status() if lr else {}

@router.get("/llm/connectivity")
async def llm_connectivity(request: Request):
    kernel = get_kernel(request)
    am = kernel.subsystems.get("agents")
    if am and hasattr(am, "llm"):
        return await am.llm.check_connectivity()
    return {"error": "LLM not available"}

class SwitchProviderRequest(BaseModel):
    provider: str

@router.post("/llm/switch")
async def switch_provider(req: SwitchProviderRequest, request: Request):
    kernel = get_kernel(request)
    am = kernel.subsystems.get("agents")
    if am and hasattr(am, "llm"):
        success = am.llm.switch_provider(req.provider)
        return {"success": success, "provider": am.llm.provider}
    return {"error": "LLM not available"}


# ── Dialogue State ───────────────────────────────────────────────

@router.get("/dialogue/contexts")
async def dialogue_contexts(request: Request):
    kernel = get_kernel(request)
    dm = kernel.subsystems.get("dialogue")
    return dm.get_all_contexts() if dm else {}


# ── Plugins ──────────────────────────────────────────────────────

@router.get("/plugins")
async def list_plugins(request: Request):
    kernel = get_kernel(request)
    pm = kernel.subsystems.get("plugins")
    return pm.get_plugin_list() if pm else []

@router.post("/plugins/discover")
async def discover_plugins(request: Request):
    kernel = get_kernel(request)
    pm = kernel.subsystems.get("plugins")
    if pm:
        await pm.discover_plugins()
        return {"status": "success", "plugins": pm.get_plugin_list()}
    return {"error": "Plugin manager not available"}

class PluginInstallRequest(BaseModel):
    url: str

@router.post("/plugins/install")
async def install_plugin(req: PluginInstallRequest, request: Request):
    kernel = get_kernel(request)
    pm = kernel.subsystems.get("plugins")
    if pm:
        return await pm.install_from_git(req.url)
    return {"error": "Plugin manager not available"}

@router.post("/plugins/{name}/reload")
async def reload_plugin(name: str, request: Request):
    kernel = get_kernel(request)
    pm = kernel.subsystems.get("plugins")
    if pm:
        result = await pm.reload_plugin(name)
        return {"status": "success" if result else "error"}
    return {"error": "Plugin manager not available"}


# ── Voice ────────────────────────────────────────────────────────

@router.get("/voice/status")
async def voice_status(request: Request):
    kernel = get_kernel(request)
    ve = kernel.subsystems.get("voice")
    return ve.get_status() if ve else {"enabled": False}

@router.post("/voice/barge-in")
async def voice_barge_in(request: Request):
    kernel = get_kernel(request)
    ve = kernel.subsystems.get("voice")
    if ve:
        ve.barge_in()
        return {"status": "barge_in_triggered"}
    return {"error": "Voice engine not available"}


# ── Setup / API Keys ────────────────────────────────────────────

@router.get("/setup/keys")
async def get_key_status():
    oai_key = os.environ.get("OPENAI_API_KEY", "")
    ant_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return {
        "openai": {
            "active": bool(oai_key),
            "masked": f"...{oai_key[-6:]}" if oai_key else None,
        },
        "anthropic": {
            "active": bool(ant_key),
            "masked": f"...{ant_key[-6:]}" if ant_key else None,
        },
    }

class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str

@router.post("/setup/apikey")
async def set_api_key(req: ApiKeyRequest):
    env_path = Path(__file__).parent.parent / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    env_var = f"{'OPENAI' if req.provider == 'openai' else 'ANTHROPIC'}_API_KEY"
    new_line = f"{env_var}={req.api_key}"

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_var}="):
            lines[i] = new_line
            updated = True
            break
    if not updated:
        lines.append(new_line)

    env_path.write_text("\n".join(lines) + "\n")
    os.environ[env_var] = req.api_key

    return {"status": "success", "message": f"{req.provider.capitalize()} API key saved"}
