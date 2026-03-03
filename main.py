"""
+==============================================================+
|                    JARVIS-OS v1.0                            |
|             AI Operating System - Main Entry                 |
|                  Codename: ARC REACTOR                       |
+==============================================================+
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is in path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env FIRST before any other imports that need keys
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env", override=False)
except ImportError:
    # dotenv optional — env vars can be set externally
    pass

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.requests import Request

from config import load_config
from core.kernel import get_kernel, Event
from core.system_control import SystemControl
from agents.manager import AgentManager
from voice.engine import VoiceEngine
from plugins.manager import PluginManager
from api.websocket import WebSocketManager
from api.routes import router as api_router
from setup_wizard import has_api_keys, run_terminal_setup, load_env, apply_env

# ── Logging Setup ────────────────────────────────────────────────
(ROOT_DIR / "logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT_DIR / "logs" / "jarvis.log", mode="a"),
    ]
)
logger = logging.getLogger("jarvis")

# ── FastAPI App ──────────────────────────────────────────────────
app = FastAPI(
    title="JARVIS-OS",
    description="AI Operating System with Multi-Agent Framework",
    version="1.0.0",
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "dashboard" / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT_DIR / "dashboard" / "templates"))

# Include API routes
app.include_router(api_router)


# ── Dashboard Route ──────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── WebSocket Endpoint ───────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    kernel = get_kernel()
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


# ── Startup / Shutdown Events ────────────────────────────────────
@app.on_event("startup")
async def startup():
    config = load_config()
    kernel = get_kernel()

    # Register all subsystems (order matters: plugins before agents)
    kernel.register_subsystem("system_control", SystemControl())
    kernel.register_subsystem("websocket", WebSocketManager())
    kernel.register_subsystem("plugins", PluginManager(config))
    kernel.register_subsystem("agents", AgentManager(config))
    kernel.register_subsystem("voice", VoiceEngine(config))

    # Boot the kernel
    await kernel.boot()

    logger.info("=" * 60)
    logger.info("  JARVIS-OS Dashboard available at:")
    logger.info(f"  http://localhost:{config['server']['port']}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown():
    kernel = get_kernel()
    await kernel.shutdown()


# ── Entry Point ──────────────────────────────────────────────────
def main():
    print(r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗       ██████╗ ███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝      ██╔═══██╗██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗█████╗██║   ██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║╚════╝██║   ██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║      ╚██████╔╝███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝       ╚═════╝ ╚══════╝

                AI Operating System v1.0
                Codename: ARC REACTOR
    """)

    # ── First-launch setup wizard ────────────────────────────────
    # If no API keys are configured, prompt the user interactively
    if not has_api_keys():
        run_terminal_setup()
        # Reload .env after setup
        env = load_env()
        apply_env(env)

    config = load_config()
    host = config["server"]["host"]
    port = config["server"]["port"]
    reload = config["server"].get("reload", False)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
