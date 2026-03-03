"""
JARVIS-OS Three-Tier Memory System — STM / MTM / LPM with heat scoring.

Architecture (inspired by MemoryOS):
- STM (Short-Term Memory): Current session context, auto-expires after session ends.
- MTM (Mid-Term Memory): Cross-session patterns with heat-based scoring.
- LPM (Long-Term Memory): Permanent user profile — facts KB, preferences, traits.
"""

import json
import math
import time
from datetime import datetime
from pathlib import Path


class MemoryStore:
    """Three-tier memory with heat-based scoring for intelligent retention."""

    def __init__(self, memory_dir: str = "./memory"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self._mtm_file = self.memory_dir / "mtm.json"
        self._lpm_file = self.memory_dir / "lpm.json"
        self._conversations_file = self.memory_dir / "conversations.json"
        self._tasks_file = self.memory_dir / "tasks.json"
        self._user_profile_file = self.memory_dir / "user_profile.json"

        self.stm: list[dict] = []
        self.mtm: list[dict] = self._load(self._mtm_file, [])
        self.lpm: dict = self._load(self._lpm_file, {
            "facts": [], "preferences": {}, "traits": {},
        })
        self.conversations: list[dict] = self._load(self._conversations_file, [])
        self.tasks_history: list[dict] = self._load(self._tasks_file, [])
        self.user_profile: dict = self._load(self._user_profile_file, {
            "name": None, "interests": [],
            "communication_style": "neutral", "known_facts": [],
        })

        self.vector_store = None
        self._init_vector_store()
        self._decay_mtm_heat()

    def _init_vector_store(self):
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.memory_dir / "vectors"))
            self.vector_store = client.get_or_create_collection(
                name="jarvis_memory", metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            pass

    def _load(self, path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return default
        return default

    def _save(self, path: Path, data):
        path.write_text(json.dumps(data, indent=2, default=str))

    # ── Heat Scoring ─────────────────────────────────────────────

    def _calculate_heat(self, item: dict) -> float:
        base = item.get("importance", 1.0)
        access_count = item.get("access_count", 1)
        freq_bonus = 1.0 + math.log(max(access_count, 1), 2) * 0.3
        try:
            created = datetime.fromisoformat(item.get("created_at", datetime.now().isoformat()))
            days_ago = (datetime.now() - created).total_seconds() / 86400
        except (ValueError, TypeError):
            days_ago = 0
        recency = math.exp(-0.693 * days_ago / 7.0)
        return round(base * freq_bonus * recency, 4)

    def _decay_mtm_heat(self):
        if not self.mtm:
            return
        surviving = []
        for item in self.mtm:
            heat = self._calculate_heat(item)
            item["heat"] = heat
            if heat > 2.0 and item.get("access_count", 1) >= 5:
                self.lpm["facts"].append({
                    "fact": item["content"], "category": item.get("category", "general"),
                    "source": "mtm_promotion", "promoted_at": datetime.now().isoformat(),
                })
            elif heat > 0.1:
                surviving.append(item)
        self.mtm = surviving
        self._save(self._mtm_file, self.mtm)
        self._save(self._lpm_file, self.lpm)

    # ── STM (Short-Term Memory) ──────────────────────────────────

    def stm_add(self, content: str, metadata: dict = None):
        self.stm.append({
            "content": content, "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        })
        if len(self.stm) > 100:
            self.stm = self.stm[-100:]

    def stm_get_context(self, limit: int = 20) -> list[dict]:
        return self.stm[-limit:]

    def stm_clear(self):
        for item in self.stm:
            if len(item.get("content", "")) > 50:
                self._promote_to_mtm(item["content"], item.get("metadata", {}))
        self.stm = []

    # ── MTM (Mid-Term Memory) ────────────────────────────────────

    def _promote_to_mtm(self, content: str, metadata: dict = None, importance: float = 1.0):
        for existing in self.mtm:
            if existing["content"] == content:
                existing["access_count"] = existing.get("access_count", 1) + 1
                existing["last_accessed"] = datetime.now().isoformat()
                existing["heat"] = self._calculate_heat(existing)
                self._save(self._mtm_file, self.mtm)
                return
        entry = {
            "id": f"mtm_{int(time.time() * 1000)}", "content": content,
            "metadata": metadata or {},
            "category": (metadata or {}).get("category", "general"),
            "importance": importance, "access_count": 1,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(), "heat": importance,
        }
        self.mtm.append(entry)
        if len(self.mtm) > 500:
            self.mtm.sort(key=lambda x: x.get("heat", 0))
            self.mtm = self.mtm[-500:]
        self._save(self._mtm_file, self.mtm)

    def mtm_recall(self, query: str, limit: int = 10) -> list[dict]:
        query_lower = query.lower()
        matches = []
        for item in self.mtm:
            if query_lower in item["content"].lower():
                item["access_count"] = item.get("access_count", 1) + 1
                item["last_accessed"] = datetime.now().isoformat()
                item["heat"] = self._calculate_heat(item)
                matches.append(item)
        matches.sort(key=lambda x: x.get("heat", 0), reverse=True)
        self._save(self._mtm_file, self.mtm)
        return matches[:limit]

    def mtm_get_hot(self, limit: int = 10) -> list[dict]:
        return sorted(self.mtm, key=lambda x: x.get("heat", 0), reverse=True)[:limit]

    # ── LPM (Long-Term Permanent Memory) ─────────────────────────

    def store_fact(self, fact: str, category: str = "general", source: str = "user"):
        entry = {
            "id": f"fact_{int(time.time() * 1000)}", "fact": fact,
            "category": category, "source": source,
            "timestamp": datetime.now().isoformat(),
        }
        self.lpm["facts"].append(entry)
        self._save(self._lpm_file, self.lpm)
        self._promote_to_mtm(fact, {"category": category}, importance=1.5)

    def get_facts(self, category: str = None) -> list:
        if category:
            return [f for f in self.lpm["facts"] if f.get("category") == category]
        return self.lpm["facts"]

    def set_preference(self, key: str, value):
        self.lpm["preferences"][key] = value
        self._save(self._lpm_file, self.lpm)

    def get_preference(self, key: str, default=None):
        return self.lpm["preferences"].get(key, default)

    def update_user_profile(self, updates: dict):
        for key, value in updates.items():
            if key == "interests" and isinstance(value, list):
                existing = set(self.user_profile.get("interests", []))
                existing.update(value)
                self.user_profile["interests"] = list(existing)
            elif key == "known_facts" and isinstance(value, list):
                existing = self.user_profile.get("known_facts", [])
                existing.extend(value)
                self.user_profile["known_facts"] = existing[-100:]
            else:
                self.user_profile[key] = value
        self.user_profile["last_interaction"] = datetime.now().isoformat()
        self._save(self._user_profile_file, self.user_profile)

    def get_user_profile(self) -> dict:
        return self.user_profile

    # ── Conversations ────────────────────────────────────────────

    def store_conversation(self, role: str, content: str, metadata: dict = None):
        entry = {
            "id": f"conv_{int(time.time() * 1000)}", "role": role,
            "content": content, "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.conversations.append(entry)
        if len(self.conversations) > 1000:
            self.conversations = self.conversations[-1000:]
        self._save(self._conversations_file, self.conversations)
        self.stm_add(f"{role}: {content[:200]}", metadata)
        if self.vector_store:
            try:
                self.vector_store.add(
                    documents=[content], ids=[entry["id"]],
                    metadatas=[{"role": role, "timestamp": entry["timestamp"]}]
                )
            except Exception:
                pass

    def get_recent_conversations(self, limit: int = 50) -> list:
        return self.conversations[-limit:]

    def search_conversations(self, query: str, limit: int = 10) -> list:
        if self.vector_store:
            try:
                results = self.vector_store.query(query_texts=[query], n_results=limit)
                return [
                    {"content": doc, "metadata": meta}
                    for doc, meta in zip(results["documents"][0], results["metadatas"][0])
                ]
            except Exception:
                pass
        query_lower = query.lower()
        return [c for c in self.conversations if query_lower in c["content"].lower()][-limit:]

    # ── Tasks ────────────────────────────────────────────────────

    def log_task(self, task: str, result: str, status: str, agent: str = None):
        entry = {
            "task": task, "result": result, "status": status,
            "agent": agent, "timestamp": datetime.now().isoformat(),
        }
        self.tasks_history.append(entry)
        if len(self.tasks_history) > 500:
            self.tasks_history = self.tasks_history[-500:]
        self._save(self._tasks_file, self.tasks_history)

    def get_task_history(self, limit: int = 50) -> list:
        return self.tasks_history[-limit:]

    # ── Unified Query ────────────────────────────────────────────

    def query_all_tiers(self, query: str) -> dict:
        return {
            "stm": [i for i in self.stm if query.lower() in i.get("content", "").lower()][-5:],
            "mtm": self.mtm_recall(query, limit=5),
            "lpm": [f for f in self.lpm["facts"] if query.lower() in f.get("fact", "").lower()][-5:],
            "conversations": self.search_conversations(query, limit=5),
        }

    def get_memory_stats(self) -> dict:
        return {
            "stm_count": len(self.stm), "mtm_count": len(self.mtm),
            "mtm_avg_heat": round(sum(i.get("heat", 0) for i in self.mtm) / max(len(self.mtm), 1), 3),
            "lpm_facts": len(self.lpm.get("facts", [])),
            "lpm_preferences": len(self.lpm.get("preferences", {})),
            "conversations": len(self.conversations), "tasks": len(self.tasks_history),
            "vector_store": self.vector_store is not None,
        }

    async def initialize(self, kernel):
        pass

    async def shutdown(self):
        self.stm_clear()
        self._save(self._conversations_file, self.conversations)
        self._save(self._mtm_file, self.mtm)
        self._save(self._lpm_file, self.lpm)
        self._save(self._tasks_file, self.tasks_history)
        self._save(self._user_profile_file, self.user_profile)
