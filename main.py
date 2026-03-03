"""
JARVIS-OS — Main Entry Point
Boots the kernel, mounts the dashboard, and starts the server.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from core.kernel import Kernel
from core.memory import MemoryStore
from core.system_control import SystemControl
from core.action_history import ActionHistory
from core.goals import GoalManager
from core.llm_router import LLMRouter
from core.dialogue import DialogueManager
from agents.manager import AgentManager
from plugins.manager import PluginManager
from voice.engine import VoiceEngine
from api.websocket import WebSocketManager
from api.routes import router as api_router

# ── Configuration ────────────────────────────────────────────────
config = load_config()
system_config = config.get("system", {})

# ── Logging ──────────────────────────────────────────────────────
log_level = system_config.get("log_level", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s │ %(name)-24s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis")

# ── Kernel ───────────────────────────────────────────────────────
kernel = Kernel(config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot and shutdown the JARVIS-OS kernel."""
    logger.info("=" * 60)
    logger.info("  JARVIS-OS  —  AI Operating System")
    logger.info("  Codename: %s", system_config.get("codename", "ARC REACTOR"))
    logger.info("=" * 60)

    # Register subsystems (order matters)
    memory_dir = system_config.get("memory_dir", "./memory")
    data_dir = system_config.get("data_dir", "./data")

    kernel.register_subsystem("memory", MemoryStore(memory_dir))
    kernel.register_subsystem("system_control", SystemControl())
    kernel.register_subsystem("websocket", WebSocketManager())
    kernel.register_subsystem("action_history", ActionHistory(data_dir))
    kernel.register_subsystem("goals", GoalManager(data_dir))
    kernel.register_subsystem("llm_router", LLMRouter(config))
    kernel.register_subsystem("dialogue", DialogueManager())
    kernel.register_subsystem("plugins", PluginManager(config))   # Before agents
    kernel.register_subsystem("agents", AgentManager(config))     # After plugins
    kernel.register_subsystem("voice", VoiceEngine(config))

    await kernel.boot()

    logger.info("All subsystems online — JARVIS-OS ready")
    logger.info("Dashboard: http://%s:%s", config["server"]["host"], config["server"]["port"])

    yield

    logger.info("Shutting down JARVIS-OS...")
    await kernel.shutdown()


# ── FastAPI App ──────────────────────────────────────────────────
app = FastAPI(title="JARVIS-OS", version="1.0.0", lifespan=lifespan)

# Mount static files and templates
dashboard_dir = Path(__file__).parent / "dashboard"
app.mount("/static", StaticFiles(directory=str(dashboard_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(dashboard_dir / "templates"))

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/")
async def dashboard(request: __import__("starlette.requests", fromlist=["Request"]).Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    ws_manager = kernel.subsystems.get("websocket")
    if not ws_manager:
        await ws.close()
        return

    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            await ws_manager.handle_message(ws, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(ws)


# ── Check first-run setup ────────────────────────────────────────
def check_setup():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        # Check if API keys are set via environment
        if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
            logger.info("No API keys configured. Starting setup wizard...")
            try:
                from setup_wizard import run_setup
                run_setup()
            except ImportError:
                logger.warning("Setup wizard not found. Set API keys manually in .env")
            except Exception:
                logger.warning("Setup wizard failed. Set API keys manually in .env")


if __name__ == "__main__":
    check_setup()

    server_config = config.get("server", {})
    uvicorn.run(
        "main:app",
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8000),
        reload=server_config.get("reload", False),
        log_level="info",
    )
