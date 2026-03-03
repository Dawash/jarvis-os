"""
JARVIS-OS Plugin: Code Runner
Executes Python code in a sandboxed subprocess with timeout protection.
"""

import asyncio
import logging
import tempfile
import os
from pathlib import Path

logger = logging.getLogger("jarvis.plugin.code_runner")

PLUGIN_INFO = {
    "name": "Code Runner",
    "version": "1.0.0",
    "description": "Execute Python code safely in a sandboxed subprocess",
    "author": "JARVIS-OS",
    "capabilities": ["code_execution", "python"],
}


def get_tools():
    return [
        {
            "name": "run_python",
            "description": "Execute Python code in a sandboxed environment. Returns stdout, stderr, and return code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30, max 120)"},
                },
                "required": ["code"],
            },
        },
    ]


async def execute(tool_name: str, arguments: dict, context: dict) -> dict:
    if tool_name == "run_python":
        return await _run_python(
            arguments.get("code", ""),
            arguments.get("timeout", 30),
        )
    return {"error": f"Unknown tool: {tool_name}"}


async def _run_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code in a subprocess with timeout."""
    timeout = min(max(timeout, 5), 120)  # Clamp 5-120 seconds

    # Write code to a temp file
    tmp_dir = tempfile.mkdtemp(prefix="jarvis_code_")
    code_path = os.path.join(tmp_dir, "script.py")

    try:
        with open(code_path, "w") as f:
            f.write(code)

        process = await asyncio.create_subprocess_exec(
            "python3", code_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmp_dir,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "status": "timeout",
                "message": f"Code execution timed out after {timeout}s",
                "stdout": "",
                "stderr": "",
                "return_code": -1,
            }

        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()

        # Truncate large outputs
        if len(stdout_text) > 10000:
            stdout_text = stdout_text[:10000] + "\n... [output truncated]"
        if len(stderr_text) > 5000:
            stderr_text = stderr_text[:5000] + "\n... [error truncated]"

        return {
            "status": "success" if process.returncode == 0 else "error",
            "stdout": stdout_text,
            "stderr": stderr_text,
            "return_code": process.returncode,
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        # Clean up temp files
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


async def on_load(kernel):
    logger.info("Code Runner plugin loaded")


async def on_unload():
    logger.info("Code Runner plugin unloaded")
