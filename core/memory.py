"""
JARVIS-OS Memory System — Persistent memory with vector search.
Allows JARVIS to remember conversations, facts, and context.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class MemoryStore:
    """
    Long-term memory using JSON-based storage with optional vector search.
    Falls back gracefully if ChromaDB is unavailable.
    """

    def __init__(self, memory_dir: str = "./memory"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.conversations_file = self.memory_dir / "conversations.json"
        self.facts_file = self.memory_dir / "facts.json"
        self.tasks_file = self.memory_dir / "tasks.json"
        self.preferences_file = self.memory_dir / "preferences.json"

        self.conversations = self._load(self.conversations_file, [])
        self.facts = self._load(self.facts_file, [])
        self.tasks_history = self._load(self.tasks_file, [])
        self.preferences = self._load(self.preferences_file, {})

        # Try to initialize vector store
        self.vector_store = None
        self._init_vector_store()

    def _init_vector_store(self):
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.memory_dir / "vectors"))
            self.vector_store = client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            pass  # Vector store optional — graceful degradation

    def _load(self, path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return default
        return default

    def _save(self, path: Path, data):
        path.write_text(json.dumps(data, indent=2, default=str))

    # ── Conversations ────────────────────────────────────────────

    def store_conversation(self, role: str, content: str, metadata: dict = None):
        entry = {
            "id": f"conv_{int(time.time() * 1000)}",
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.conversations.append(entry)
        # Keep last 1000 conversations in file
        if len(self.conversations) > 1000:
            self.conversations = self.conversations[-1000:]
        self._save(self.conversations_file, self.conversations)

        # Also store in vector DB for semantic search
        if self.vector_store:
            try:
                self.vector_store.add(
                    documents=[content],
                    ids=[entry["id"]],
                    metadatas=[{"role": role, "timestamp": entry["timestamp"]}]
                )
            except Exception:
                pass

    def get_recent_conversations(self, limit: int = 50) -> list:
        return self.conversations[-limit:]

    def search_conversations(self, query: str, limit: int = 10) -> list:
        if self.vector_store:
            try:
                results = self.vector_store.query(
                    query_texts=[query],
                    n_results=limit,
                )
                return [
                    {"content": doc, "metadata": meta}
                    for doc, meta in zip(
                        results["documents"][0], results["metadatas"][0]
                    )
                ]
            except Exception:
                pass
        # Fallback: simple text search
        query_lower = query.lower()
        matches = [c for c in self.conversations if query_lower in c["content"].lower()]
        return matches[-limit:]

    # ── Facts ────────────────────────────────────────────────────

    def store_fact(self, fact: str, category: str = "general", source: str = "user"):
        entry = {
            "id": f"fact_{int(time.time() * 1000)}",
            "fact": fact,
            "category": category,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        }
        self.facts.append(entry)
        self._save(self.facts_file, self.facts)

    def get_facts(self, category: str = None) -> list:
        if category:
            return [f for f in self.facts if f["category"] == category]
        return self.facts

    # ── Tasks ────────────────────────────────────────────────────

    def log_task(self, task: str, result: str, status: str, agent: str = None):
        entry = {
            "task": task,
            "result": result,
            "status": status,
            "agent": agent,
            "timestamp": datetime.now().isoformat(),
        }
        self.tasks_history.append(entry)
        if len(self.tasks_history) > 500:
            self.tasks_history = self.tasks_history[-500:]
        self._save(self.tasks_file, self.tasks_history)

    def get_task_history(self, limit: int = 50) -> list:
        return self.tasks_history[-limit:]

    # ── Preferences ──────────────────────────────────────────────

    def set_preference(self, key: str, value):
        self.preferences[key] = value
        self._save(self.preferences_file, self.preferences)

    def get_preference(self, key: str, default=None):
        return self.preferences.get(key, default)

    async def initialize(self, kernel):
        pass

    async def shutdown(self):
        self._save(self.conversations_file, self.conversations)
        self._save(self.facts_file, self.facts)
        self._save(self.tasks_file, self.tasks_history)
        self._save(self.preferences_file, self.preferences)
