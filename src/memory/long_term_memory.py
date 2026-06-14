"""Long-term persistent memory — facts survive program restarts via local JSON storage."""
from __future__ import annotations
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MEMORY_PATH = str(Path(__file__).resolve().parent.parent.parent / "memory" / "long_term.json")


class LongTermMemory:
    """Persistent key-value memory backed by a local JSON file.

    Each fact is a dict: {id, content, timestamp}.
    Atomic writes via temp-file + os.replace.
    """

    def __init__(self, memory_path: str | None = None) -> None:
        self._path = Path(memory_path or DEFAULT_MEMORY_PATH)
        self._facts: list[dict] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_fact(self, content: str) -> str:
        """Append a fact and return its id. Does NOT auto-save."""
        fact_id = uuid.uuid4().hex[:12]
        self._facts.append({
            "id": fact_id,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return fact_id

    def remove_fact(self, fact_id: str) -> bool:
        """Delete a fact by id. Returns whether it was found."""
        before = len(self._facts)
        self._facts = [f for f in self._facts if f["id"] != fact_id]
        return len(self._facts) < before

    def update_fact(self, fact_id: str, new_content: str) -> bool:
        """Replace the content of a fact and refresh its timestamp. Returns whether found."""
        for fact in self._facts:
            if fact["id"] == fact_id:
                fact["content"] = new_content
                fact["timestamp"] = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def get_all_facts(self) -> list[dict]:
        """Return all facts (ordered oldest → newest)."""
        return list(self._facts)

    def format_for_prompt(self) -> str:
        """Return a string suitable for injection into the system prompt.

        Capped at the 20 most recent facts. Returns empty string when empty.
        """
        facts = self._facts[-20:] if len(self._facts) > 20 else self._facts
        if not facts:
            return ""
        lines = ["", "[长期记忆 — 以下是关于用户的已知信息]"]
        for f in facts:
            lines.append(f"- {f['content']}")
        return "\n".join(lines)

    def save(self) -> None:
        """Atomic write — temp file then os.replace."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"facts": self._facts}, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

    def clear(self) -> None:
        """Discard all facts and persist."""
        self._facts = []
        self.save()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._facts = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._facts = data.get("facts", [])
        except (json.JSONDecodeError, OSError):
            self._facts = []
