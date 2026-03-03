"""
JARVIS-OS API Routes — REST + WebSocket endpoints for the entire OS.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.kernel import get_kernel
from setup_wizard import save_api_key, get_configured_providers, get_masked_keys

router = APIRouter(prefix="/api")


# ── Request Models ───────────────────────────────────────────────
class CommandRequest(BaseModel):
    command: str
    source: str = "dashboard"

class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str

class ExecuteRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: int = 60

class SpawnAgentRequest(BaseModel):
    task: str
    type: str = "general"
    name: Optional[str] = None

class CreatePluginRequest(BaseModel):
    name: str
    description: str
    capabilities: list = []
    code: Optional[str] = None

class FileWriteRequest(BaseModel):
    path: str
    content: str


# ── System ───────────────────────────────────────────────────────
@router.get("/system/info")
async def system_info():
    kernel = get_kernel()
    return kernel.get_system_info()

@router.get("/system/stats")
async def system_stats():
    kernel = get_kernel()
    sc = kernel.subsystems.get("system_control")
    if sc:
        return sc.get_system_stats()
    return {"error": "System control not available"}

@router.get("/system/processes")
async def system_processes(sort_by: str = "cpu_percent", limit: int = 20):
    kernel = get_kernel()
    sc = kernel.subsystems.get("system_control")
    if sc:
        return sc.get_processes(sort_by=sort_by, limit=limit)
    return []

@router.post("/system/restart")
async def system_restart():
    kernel = get_kernel()
    await kernel.emit_event(type("Event", (), {"type": "system.restart", "data": {}, "source": "api", "timestamp": ""})())
    return {"status": "restarting"}

@router.post("/system/shutdown")
async def system_shutdown():
    kernel = get_kernel()
    asyncio.create_task(kernel.shutdown())
    return {"status": "shutting_down"}


# ── Commands ─────────────────────────────────────────────────────
@router.post("/command")
async def process_command(req: CommandRequest):
    kernel = get_kernel()
    result = await kernel.process_command(req.command, req.source)
    return result


# ── Shell Execution ──────────────────────────────────────────────
@router.post("/execute")
async def execute_command(req: ExecuteRequest):
    kernel = get_kernel()
    sc = kernel.subsystems.get("system_control")
    if sc:
        result = await sc.execute_command(req.command, cwd=req.cwd, timeout=req.timeout)
        return result
    return {"error": "System control not available"}


# ── Files ────────────────────────────────────────────────────────
@router.get("/files/list")
async def list_files(path: str = "/"):
    kernel = get_kernel()
    sc = kernel.subsystems.get("system_control")
    if sc:
        try:
            items = sc.list_directory(path)
            resolved = str(Path(path).resolve())
            return {"items": items, "current_path": resolved}
        except Exception as e:
            return {"error": str(e), "items": []}
    return {"error": "System control not available"}

@router.get("/files/read")
async def read_file(path: str):
    kernel = get_kernel()
    sc = kernel.subsystems.get("system_control")
    if sc:
        return sc.read_file(path)
    return {"error": "System control not available"}

@router.post("/files/write")
async def write_file(req: FileWriteRequest):
    kernel = get_kernel()
    sc = kernel.subsystems.get("system_control")
    if sc:
        return sc.write_file(req.path, req.content)
    return {"error": "System control not available"}

@router.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    upload_dir = Path("./data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for f in files:
        dest = upload_dir / f.filename
        with open(dest, "wb") as buf:
            content = await f.read()
            buf.write(content)
        uploaded.append({
            "name": f.filename,
            "path": str(dest.resolve()),
            "size": len(content),
            "content_type": f.content_type,
        })

    return {"status": "success", "files": uploaded}


# ── Agents ───────────────────────────────────────────────────────
@router.get("/agents")
async def list_agents():
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am:
        return am.get_all_agents()
    return []

@router.get("/agents/active")
async def active_agents():
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am:
        return am.get_active_agents()
    return []

@router.post("/agents/spawn")
async def spawn_agent(req: SpawnAgentRequest):
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am:
        agent = await am.spawn_agent(req.task, req.type, req.name)
        # Run in background
        asyncio.create_task(am._run_agent(agent))
        return {"status": "spawned", "agent": agent.to_dict()}
    return {"error": "Agent manager not available"}

@router.post("/agents/{agent_id}/cancel")
async def cancel_agent(agent_id: str):
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am:
        success = am.cancel_agent(agent_id)
        return {"status": "cancelled" if success else "not_found"}
    return {"error": "Agent manager not available"}


# ── Memory ───────────────────────────────────────────────────────
@router.get("/memory/conversations")
async def get_conversations(limit: int = 50):
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am and am.memory:
        return am.memory.get_recent_conversations(limit)
    return []

@router.get("/memory/facts")
async def get_facts(category: Optional[str] = None):
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am and am.memory:
        return am.memory.get_facts(category)
    return []

@router.get("/memory/tasks")
async def get_task_history(limit: int = 50):
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am and am.memory:
        return am.memory.get_task_history(limit)
    return []

@router.get("/memory/search")
async def search_memory(query: str, limit: int = 10):
    kernel = get_kernel()
    am = kernel.subsystems.get("agents")
    if am and am.memory:
        return am.memory.search_conversations(query, limit)
    return []


# ── Plugins ──────────────────────────────────────────────────────
@router.get("/plugins")
async def list_plugins():
    kernel = get_kernel()
    pm = kernel.subsystems.get("plugins")
    if pm:
        return pm.get_all_plugins()
    return []

@router.post("/plugins/create")
async def create_plugin(req: CreatePluginRequest):
    kernel = get_kernel()
    pm = kernel.subsystems.get("plugins")
    if pm:
        return await pm.create_plugin(req.name, req.description, req.capabilities, req.code)
    return {"error": "Plugin manager not available"}

@router.post("/plugins/discover")
async def discover_plugins():
    kernel = get_kernel()
    pm = kernel.subsystems.get("plugins")
    if pm:
        await pm.discover_and_load()
        return {"status": "success", "plugins": pm.get_all_plugins()}
    return {"error": "Plugin manager not available"}


# ── Voice ────────────────────────────────────────────────────────
@router.get("/voice/status")
async def voice_status():
    kernel = get_kernel()
    ve = kernel.subsystems.get("voice")
    if ve:
        return ve.get_status()
    return {"enabled": False}

@router.post("/voice/toggle")
async def toggle_voice():
    kernel = get_kernel()
    ve = kernel.subsystems.get("voice")
    if ve:
        if ve.is_listening:
            ve.stop_listening()
        else:
            ve.start_listening()
        return ve.get_status()
    return {"error": "Voice engine not available"}

@router.post("/voice/speak")
async def speak(text: str = Form(...)):
    kernel = get_kernel()
    ve = kernel.subsystems.get("voice")
    if ve:
        await ve.speak_async(text)
        return {"status": "speaking"}
    return {"error": "Voice engine not available"}

@router.post("/voice/barge-in")
async def voice_barge_in():
    """Interrupt TTS immediately (barge-in)."""
    kernel = get_kernel()
    ve = kernel.subsystems.get("voice")
    if ve:
        ve.barge_in()
        return {"status": "interrupted", "was_speaking": ve.is_speaking}
    return {"error": "Voice engine not available"}


# ── Setup / API Keys ────────────────────────────────────────────
@router.get("/setup/status")
async def setup_status():
    """Check if API keys are configured — used by dashboard first-boot."""
    return get_configured_providers()

@router.get("/setup/keys")
async def get_keys():
    """Return masked API keys for display in Settings."""
    providers = get_configured_providers()
    masked = get_masked_keys()
    return {
        "openai": {"active": providers["openai"], "masked": masked["openai"]},
        "anthropic": {"active": providers["anthropic"], "masked": masked["anthropic"]},
    }

@router.post("/setup/apikey")
async def set_api_key(req: ApiKeyRequest):
    """Save an API key from the dashboard setup wizard."""
    result = save_api_key(req.provider, req.api_key)
    return result
