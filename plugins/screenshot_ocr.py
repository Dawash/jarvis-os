"""
JARVIS-OS Plugin: Screenshot & Vision
Take screenshots and analyze images using LLM vision API (GPT-4o / Claude).
"""

import logging
import base64
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("jarvis.plugin.screenshot")

PLUGIN_INFO = {
    "name": "Screenshot & Vision",
    "version": "2.0.0",
    "description": "Take screenshots and analyze screen content with AI vision",
    "author": "JARVIS-OS",
    "capabilities": ["screenshot", "image_analysis", "vision"],
}

_kernel = None


def get_tools():
    return [
        {
            "name": "take_screenshot",
            "description": "Take a screenshot of the current screen and optionally analyze it with AI vision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional region {x, y, width, height}",
                        "properties": {
                            "x": {"type": "integer"}, "y": {"type": "integer"},
                            "width": {"type": "integer"}, "height": {"type": "integer"},
                        },
                    },
                    "analyze": {
                        "type": "boolean",
                        "description": "If true, analyze the screenshot with AI vision (default: true)",
                    },
                    "question": {
                        "type": "string",
                        "description": "What to analyze about the screenshot",
                    },
                },
            },
        },
        {
            "name": "analyze_image",
            "description": "Analyze an image file using AI vision and describe its contents.",
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
        return await _take_screenshot(
            arguments.get("region"),
            arguments.get("analyze", True),
            arguments.get("question", "Describe what you see on this screen."),
        )
    elif tool_name == "analyze_image":
        return await _analyze_image(
            arguments.get("path", ""),
            arguments.get("question", "Describe this image in detail."),
        )
    return {"error": f"Unknown tool: {tool_name}"}


async def _take_screenshot(region=None, analyze=True, question="Describe what you see.") -> dict:
    try:
        import pyautogui
        timestamp = int(datetime.now().timestamp())
        output_path = f"/tmp/jarvis_screenshot_{timestamp}.png"

        if region:
            screenshot = pyautogui.screenshot(region=(
                region.get("x", 0), region.get("y", 0),
                region.get("width", 1920), region.get("height", 1080),
            ))
        else:
            screenshot = pyautogui.screenshot()

        screenshot.save(output_path)
        result = {
            "status": "success",
            "path": output_path,
            "size": {"width": screenshot.width, "height": screenshot.height},
        }

        # Analyze with vision API if requested
        if analyze and _kernel:
            analysis = await _call_vision_api(output_path, question)
            result["analysis"] = analysis

        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _analyze_image(path: str, question: str) -> dict:
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"Image not found: {path}"}

        if not _kernel:
            return {"error": "Kernel not available for vision API"}

        analysis = await _call_vision_api(path, question)
        return {
            "status": "success",
            "path": path,
            "size_bytes": p.stat().st_size,
            "analysis": analysis,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _call_vision_api(image_path: str, question: str) -> str:
    """Send image to LLM vision API (OpenAI GPT-4o or Anthropic Claude)."""
    p = Path(image_path)
    image_data = base64.b64encode(p.read_bytes()).decode()
    suffix = p.suffix.lower()
    media_type = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp",
    }.get(suffix, "image/png")

    # Get LLM provider from kernel
    am = _kernel.subsystems.get("agents")
    if not am or not hasattr(am, "llm"):
        return "Vision API not available — no LLM provider configured"

    llm = am.llm
    provider = llm.provider

    try:
        if provider == "openai":
            response = await llm.client.chat.completions.create(
                model=llm.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{media_type};base64,{image_data}",
                        }},
                    ],
                }],
                max_tokens=1000,
            )
            return response.choices[0].message.content

        elif provider == "anthropic":
            response = await llm.client.messages.create(
                model=llm.model,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": media_type,
                            "data": image_data,
                        }},
                        {"type": "text", "text": question},
                    ],
                }],
            )
            return response.content[0].text

        else:
            return f"Vision not supported for provider: {provider}"

    except Exception as e:
        logger.error(f"Vision API error: {e}")
        # Fallback to OCR if available
        try:
            return await _ocr_fallback(image_path)
        except Exception:
            return f"Vision analysis failed: {str(e)}"


async def _ocr_fallback(image_path: str) -> str:
    """Fallback OCR using Tesseract if available."""
    try:
        import subprocess
        result = subprocess.run(
            ["tesseract", image_path, "stdout"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"[OCR fallback] {result.stdout.strip()}"
        return "Could not analyze image (vision API unavailable, OCR returned no text)"
    except FileNotFoundError:
        return "Could not analyze image (vision API unavailable, tesseract not installed)"
    except Exception as e:
        return f"OCR fallback failed: {str(e)}"


async def on_load(kernel):
    global _kernel
    _kernel = kernel
    logger.info("Screenshot & Vision plugin loaded (v2.0 with LLM vision)")


async def on_unload():
    logger.info("Screenshot & Vision plugin unloaded")
