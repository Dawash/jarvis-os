"""
JARVIS-OS LLM Provider — Unified interface for OpenAI, Anthropic, and Ollama (offline).
Supports tool calling, streaming, and graceful degradation to local models.
"""

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger("jarvis.llm")


class LLMProvider:
    """Unified LLM interface with online/offline support."""

    def __init__(self, config: dict):
        self.config = config.get("llm", {})
        self.provider = self.config.get("default_provider", "openai")
        self.client = None
        self.model = None
        self.max_tokens = 4096
        self.temperature = 0.7
        self._offline_mode = False
        self._ollama_available = False

        self._init_provider()

    def _init_provider(self):
        """Initialize the configured LLM provider, with fallback to offline."""
        # Try primary provider
        if self.provider == "openai":
            success = self._init_openai()
        elif self.provider == "anthropic":
            success = self._init_anthropic()
        elif self.provider == "ollama":
            success = self._init_ollama()
        else:
            success = self._init_openai()

        # Fallback chain: configured → ollama → offline
        if not success:
            logger.warning(f"Primary provider '{self.provider}' failed, trying fallback...")
            if self.provider != "ollama" and self._try_ollama():
                logger.info("Fell back to Ollama (local)")
            else:
                logger.warning("No LLM provider available — limited functionality")
                self._offline_mode = True

    def _init_openai(self) -> bool:
        try:
            from openai import AsyncOpenAI
            api_key = self.config.get("openai", {}).get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return False
            self.client = AsyncOpenAI(api_key=api_key)
            oai_config = self.config.get("openai", {})
            self.model = oai_config.get("model", "gpt-4o")
            self.max_tokens = oai_config.get("max_tokens", 4096)
            self.temperature = oai_config.get("temperature", 0.7)
            self.provider = "openai"
            logger.info(f"LLM Provider: OpenAI ({self.model})")
            return True
        except Exception as e:
            logger.warning(f"OpenAI init failed: {e}")
            return False

    def _init_anthropic(self) -> bool:
        try:
            from anthropic import AsyncAnthropic
            api_key = self.config.get("anthropic", {}).get("api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return False
            self.client = AsyncAnthropic(api_key=api_key)
            ant_config = self.config.get("anthropic", {})
            self.model = ant_config.get("model", "claude-sonnet-4-20250514")
            self.max_tokens = ant_config.get("max_tokens", 4096)
            self.temperature = ant_config.get("temperature", 0.7)
            self.provider = "anthropic"
            logger.info(f"LLM Provider: Anthropic ({self.model})")
            return True
        except Exception as e:
            logger.warning(f"Anthropic init failed: {e}")
            return False

    def _init_ollama(self) -> bool:
        return self._try_ollama()

    def _try_ollama(self) -> bool:
        """Try to connect to a local Ollama instance."""
        try:
            import httpx
            # Synchronous check
            with httpx.Client(timeout=3) as client:
                resp = client.get("http://localhost:11434/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    if models:
                        self.model = models[0]["name"]
                        self.provider = "ollama"
                        self._ollama_available = True
                        self._offline_mode = False
                        logger.info(f"LLM Provider: Ollama ({self.model})")
                        return True
        except Exception:
            pass
        return False

    @property
    def is_offline(self) -> bool:
        return self._offline_mode

    @property
    def is_available(self) -> bool:
        return self.client is not None or self._ollama_available

    async def chat(self, messages: list, tools: list = None, stream: bool = False) -> dict:
        """Send a chat completion request to the configured provider."""
        if self._offline_mode:
            return {"content": "I'm currently in offline mode with no LLM provider available. Please configure an API key or start Ollama."}

        if self.provider == "openai":
            return await self._chat_openai(messages, tools, stream)
        elif self.provider == "anthropic":
            return await self._chat_anthropic(messages, tools, stream)
        elif self.provider == "ollama":
            return await self._chat_ollama(messages, tools, stream)
        else:
            return {"error": f"Unknown provider: {self.provider}"}

    async def _chat_openai(self, messages: list, tools: list = None, stream: bool = False) -> dict:
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
            if tools:
                kwargs["tools"] = [
                    {"type": "function", "function": t} for t in tools
                ]
                kwargs["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            result = {"content": msg.content or ""}
            if msg.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in msg.tool_calls
                ]
            return result

        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            # Try fallback to Ollama
            if self._try_ollama():
                return await self._chat_ollama(messages, tools, stream)
            return {"error": str(e)}

    async def _chat_anthropic(self, messages: list, tools: list = None, stream: bool = False) -> dict:
        try:
            system_msg = ""
            chat_messages = []
            for m in messages:
                if m["role"] == "system":
                    system_msg += m["content"] + "\n"
                else:
                    chat_messages.append(m)

            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": chat_messages,
            }
            if system_msg:
                kwargs["system"] = system_msg.strip()
            if tools:
                kwargs["tools"] = [
                    {"name": t["name"], "description": t.get("description", ""),
                     "input_schema": t.get("parameters", {})}
                    for t in tools
                ]

            response = await self.client.messages.create(**kwargs)

            result = {"content": ""}
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    result["content"] += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id, "name": block.name,
                        "arguments": __import__("json").dumps(block.input),
                    })
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result

        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            if self._try_ollama():
                return await self._chat_ollama(messages, tools, stream)
            return {"error": str(e)}

    async def _chat_ollama(self, messages: list, tools: list = None, stream: bool = False) -> dict:
        """Chat using local Ollama instance."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": self.temperature},
                }

                resp = await client.post(
                    "http://localhost:11434/api/chat",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"content": data.get("message", {}).get("content", "")}
                else:
                    return {"error": f"Ollama error: {resp.status_code}"}

        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            self._offline_mode = True
            return {"error": f"Ollama unavailable: {str(e)}"}

    async def check_connectivity(self) -> dict:
        """Check which LLM providers are available."""
        status = {"openai": False, "anthropic": False, "ollama": False}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                try:
                    resp = await client.get("http://localhost:11434/api/tags")
                    status["ollama"] = resp.status_code == 200
                except Exception:
                    pass
        except ImportError:
            pass

        oai_key = self.config.get("openai", {}).get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        ant_key = self.config.get("anthropic", {}).get("api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        status["openai"] = bool(oai_key)
        status["anthropic"] = bool(ant_key)

        return {
            "current_provider": self.provider,
            "model": self.model,
            "offline_mode": self._offline_mode,
            "providers": status,
        }

    def switch_provider(self, provider: str) -> bool:
        """Switch to a different provider at runtime."""
        old = self.provider
        self.provider = provider
        self._offline_mode = False

        if provider == "openai":
            success = self._init_openai()
        elif provider == "anthropic":
            success = self._init_anthropic()
        elif provider == "ollama":
            success = self._init_ollama()
        else:
            success = False

        if not success:
            self.provider = old
            return False
        return True
