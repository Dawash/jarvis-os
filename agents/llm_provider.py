"""
JARVIS-OS LLM Provider — Unified interface for multiple LLM backends.
Supports OpenAI, Anthropic, and extensible to others.
"""

import json
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger("jarvis.llm")


class LLMProvider:
    """Unified LLM interface supporting multiple providers."""

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("default_provider", "openai")
        self._openai_client = None
        self._anthropic_client = None

    def _get_openai(self):
        if not self._openai_client:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(
                api_key=self.config["openai"]["api_key"]
            )
        return self._openai_client

    def _get_anthropic(self):
        if not self._anthropic_client:
            from anthropic import AsyncAnthropic
            self._anthropic_client = AsyncAnthropic(
                api_key=self.config["anthropic"]["api_key"]
            )
        return self._anthropic_client

    async def chat(
        self,
        messages: list,
        system: str = None,
        tools: list = None,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        provider: str = None,
    ) -> dict:
        """Send a chat completion request."""
        use_provider = provider or self.provider
        if use_provider == "openai":
            return await self._chat_openai(messages, system, tools, model, temperature, max_tokens)
        elif use_provider == "anthropic":
            return await self._chat_anthropic(messages, system, tools, model, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {use_provider}")

    async def _chat_openai(self, messages, system, tools, model, temperature, max_tokens) -> dict:
        cfg = self.config["openai"]
        client = self._get_openai()

        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        kwargs = {
            "model": model or cfg["model"],
            "messages": msgs,
            "temperature": temperature if temperature is not None else cfg.get("temperature", 0.7),
            "max_tokens": max_tokens or cfg.get("max_tokens", 4096),
        }

        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        result = {
            "content": choice.message.content or "",
            "role": "assistant",
            "tool_calls": [],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        }

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        return result

    async def _chat_anthropic(self, messages, system, tools, model, temperature, max_tokens) -> dict:
        cfg = self.config["anthropic"]
        client = self._get_anthropic()

        kwargs = {
            "model": model or cfg["model"],
            "messages": messages,
            "max_tokens": max_tokens or cfg.get("max_tokens", 4096),
            "temperature": temperature if temperature is not None else cfg.get("temperature", 0.7),
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {}),
                }
                for t in tools
            ]

        response = await client.messages.create(**kwargs)

        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        return {
            "content": content,
            "role": "assistant",
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            }
        }

    async def stream_chat(
        self,
        messages: list,
        system: str = None,
        model: str = None,
        provider: str = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat response token by token."""
        use_provider = provider or self.provider
        if use_provider == "openai":
            async for token in self._stream_openai(messages, system, model):
                yield token
        elif use_provider == "anthropic":
            async for token in self._stream_anthropic(messages, system, model):
                yield token

    async def _stream_openai(self, messages, system, model):
        cfg = self.config["openai"]
        client = self._get_openai()
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        stream = await client.chat.completions.create(
            model=model or cfg["model"],
            messages=msgs,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _stream_anthropic(self, messages, system, model):
        cfg = self.config["anthropic"]
        client = self._get_anthropic()
        kwargs = {
            "model": model or cfg["model"],
            "messages": messages,
            "max_tokens": cfg.get("max_tokens", 4096),
        }
        if system:
            kwargs["system"] = system

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
