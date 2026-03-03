"""
JARVIS-OS Plugin: Screenshot & Vision
Take screenshots and analyze images using vision capabilities.
"""

import logging
import base64
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("jarvis.plugin.screenshot")

PLUGIN_INFO = {
    "name": "Screenshot & Vision",
    "version": "1.0.0",
    "description": "Take screenshots and analyze screen content",
    "author": "JARVIS-OS",
    "capabilities": ["screenshot", "image_analysis"],
}


def get_tools():
    return [
        {
            "name": "take_screenshot",
            "description": "Take a screenshot of the current screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional region {x, y, width, height}",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                    },
                },
            },
        },
        {
            "name": "analyze_image",
            "description": "Analyze an image file and describe its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the image file"},
                    "question": {"type": "string", "description": "What to analyze about the image"},
                },
                "required": ["path"],
            },
        },
    ]


async def execute(tool_name: str, arguments: dict, context: dict) -> dict:
    if tool_name == "take_screenshot":
        return await _take_screenshot(arguments.get("region"))
    elif tool_name == "analyze_image":
        return await _analyze_image(arguments.get("path", ""), arguments.get("question", "Describe this image"))
    return {"error": f"Unknown tool: {tool_name}"}


async def _take_screenshot(region=None) -> dict:
    try:
        import pyautogui
        timestamp = int(datetime.now().timestamp())
        output_path = f"/tmp/jarvis_screenshot_{timestamp}.png"

        if region:
            screenshot = pyautogui.screenshot(region=(
                region.get("x", 0),
                region.get("y", 0),
                region.get("width", 1920),
                region.get("height", 1080),
            ))
        else:
            screenshot = pyautogui.screenshot()

        screenshot.save(output_path)
        return {
            "status": "success",
            "path": output_path,
            "size": {"width": screenshot.width, "height": screenshot.height},
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _analyze_image(path: str, question: str) -> dict:
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"Image not found: {path}"}

        # Read and encode image
        image_data = base64.b64encode(p.read_bytes()).decode()
        suffix = p.suffix.lower()
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

        return {
            "status": "success",
            "path": path,
            "size_bytes": p.stat().st_size,
            "media_type": media_type,
            "note": "Image loaded. Use the LLM vision API to analyze the contents.",
            "question": question,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def on_load(kernel):
    logger.info("Screenshot & Vision plugin loaded")


async def on_unload():
    logger.info("Screenshot & Vision plugin unloaded")
