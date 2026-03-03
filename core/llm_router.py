"""
JARVIS-OS LLM Traffic Control — Request queue, caching, token budgeting, model routing.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum

logger = logging.getLogger("jarvis.llm_router")


class Priority(IntEnum):
    CRITICAL = 0  # System/safety
    HIGH = 1      # Voice commands (latency-sensitive)
    NORMAL = 2    # Dashboard commands
    LOW = 3       # Background tasks, scheduled


@dataclass(order=True)
class LLMRequest:
    priority: int
    timestamp: float = field(compare=False)
    messages: list = field(compare=False)
    model_hint: str = field(compare=False, default=None)
    tools: list = field(compare=False, default=None)
    future: asyncio.Future = field(compare=False, default=None)
    source: str = field(compare=False, default="dashboard")


class LLMRouter:
    """
    Intelligent LLM traffic controller with:
    - Priority queue (voice > dashboard > background)
    - Semantic response caching
    - Token budget tracking with daily limits
    - Model routing (simple → small model, complex → large model)
    """

    def __init__(self, config: dict):
        llm_config = config.get("llm", {})
        self.default_provider = llm_config.get("default_provider", "openai")

        # Token budget
        budget_config = config.get("token_budget", {})
        self.daily_limit = budget_config.get("daily_limit", 500000)
        self.warning_threshold = budget_config.get("warning_threshold", 0.8)
        self.tokens_used_today = 0
        self._budget_reset_date = datetime.now().date()

        # Response cache (LRU, max 200 entries)
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.cache_max = 200
        self.cache_ttl = 3600  # 1 hour

        # Request queue
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._processing = False

        # Stats
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "requests_by_priority": {p.name: 0 for p in Priority},
        }

        self.kernel = None
        self.llm_provider = None

    async def initialize(self, kernel):
        self.kernel = kernel
        # LLM provider will be set when agent manager connects
        am = kernel.subsystems.get("agents")
        if am and hasattr(am, "llm"):
            self.llm_provider = am.llm

    async def shutdown(self):
        pass

    def _cache_key(self, messages: list, tools: list = None) -> str:
        """Generate cache key from messages content."""
        content = json.dumps(messages[-3:], sort_keys=True, default=str)
        if tools:
            content += json.dumps([t.get("name", "") for t in tools], sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    def _check_cache(self, key: str) -> dict:
        """Check if response is cached and still valid."""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["cached_at"] < self.cache_ttl:
                self.cache.move_to_end(key)
                self.stats["cache_hits"] += 1
                return entry["response"]
            else:
                del self.cache[key]
        self.stats["cache_misses"] += 1
        return None

    def _store_cache(self, key: str, response: dict):
        """Store a response in cache."""
        self.cache[key] = {"response": response, "cached_at": time.time()}
        if len(self.cache) > self.cache_max:
            self.cache.popitem(last=False)

    def _reset_daily_budget(self):
        """Reset token budget if it's a new day."""
        today = datetime.now().date()
        if today > self._budget_reset_date:
            self.tokens_used_today = 0
            self._budget_reset_date = today

    def _classify_complexity(self, messages: list) -> str:
        """Classify request complexity for model routing."""
        if not messages:
            return "simple"
        last_msg = messages[-1].get("content", "") if messages else ""
        if isinstance(last_msg, list):
            last_msg = " ".join(str(c) for c in last_msg)
        word_count = len(last_msg.split())
        has_tools = any("tool" in str(m) for m in messages)

        if word_count < 20 and not has_tools:
            return "simple"
        elif word_count > 200 or has_tools:
            return "complex"
        return "moderate"

    def select_model(self, messages: list, model_hint: str = None) -> str:
        """Select the best model based on request complexity."""
        if model_hint:
            return model_hint
        complexity = self._classify_complexity(messages)
        # For now return default — in future could route to smaller models
        return None  # Use provider default

    async def route_request(self, messages: list, tools: list = None,
                           priority: Priority = Priority.NORMAL,
                           source: str = "dashboard",
                           model_hint: str = None,
                           use_cache: bool = True) -> dict:
        """Main entry point — route an LLM request through the traffic controller."""
        self._reset_daily_budget()
        self.stats["total_requests"] += 1
        self.stats["requests_by_priority"][priority.name] = (
            self.stats["requests_by_priority"].get(priority.name, 0) + 1
        )

        # Check token budget
        if self.tokens_used_today >= self.daily_limit:
            return {
                "error": "Daily token budget exceeded",
                "tokens_used": self.tokens_used_today,
                "limit": self.daily_limit,
            }

        # Check cache (skip for tool-calling requests)
        if use_cache and not tools:
            cache_key = self._cache_key(messages, tools)
            cached = self._check_cache(cache_key)
            if cached:
                logger.debug("LLM cache hit")
                return cached

        # Select model
        model = self.select_model(messages, model_hint)

        # Execute request directly (queue for future use with concurrent limits)
        if not self.llm_provider:
            return {"error": "LLM provider not initialized"}

        try:
            if tools:
                response = await self.llm_provider.chat(messages, tools=tools)
            else:
                response = await self.llm_provider.chat(messages)

            # Track tokens (estimate if not provided)
            input_tokens = sum(len(str(m.get("content", ""))) // 4 for m in messages)
            output_tokens = len(str(response.get("content", ""))) // 4
            self.tokens_used_today += input_tokens + output_tokens
            self.stats["tokens_input"] += input_tokens
            self.stats["tokens_output"] += output_tokens

            # Warn if approaching limit
            usage_pct = self.tokens_used_today / max(self.daily_limit, 1)
            if usage_pct >= self.warning_threshold:
                logger.warning(
                    f"Token budget at {usage_pct:.0%} ({self.tokens_used_today}/{self.daily_limit})"
                )

            # Cache the response
            if use_cache and not tools:
                self._store_cache(self._cache_key(messages, tools), response)

            return response

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return {"error": str(e)}

    def get_budget_status(self) -> dict:
        self._reset_daily_budget()
        return {
            "tokens_used": self.tokens_used_today,
            "daily_limit": self.daily_limit,
            "usage_percent": round(self.tokens_used_today / max(self.daily_limit, 1) * 100, 1),
            "remaining": max(0, self.daily_limit - self.tokens_used_today),
        }

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "budget": self.get_budget_status(),
            "cache_size": len(self.cache),
            "cache_max": self.cache_max,
        }
