"""Directory-scoped memory — per-folder notes that persist across conversations.

A separate memory layer from long-term memory: loaded only when the agent
accesses a specific directory, updated automatically after each task that
touched that directory.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "memory" / "directory_memories.json"


class DirectoryMemory:
    """Persistent per-directory memory store.

    Storage layout (JSON):
    {
      "/abs/path/to/dir": {
        "memory": "LLM-written summary of key facts about this directory",
        "updated_at": "ISO8601"
      },
      ...
    }
    """

    def __init__(self, store_path: str | None = None) -> None:
        self._path = Path(store_path or DEFAULT_PATH)
        self._data: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, dir_path: str) -> str:
        """Return stored memory text for *dir_path*, or empty string."""
        key = self._key(dir_path)
        return self._data.get(key, {}).get("memory", "")

    def has(self, dir_path: str) -> bool:
        return bool(self.get(dir_path))

    def save(self, dir_path: str, content: str) -> None:
        """Store (or overwrite) the memory for *dir_path* and persist atomically."""
        key = self._key(dir_path)
        self._data[key] = {
            "memory": content,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_atomic()

    def delete(self, dir_path: str) -> bool:
        """Remove the memory for *dir_path*. Returns True if it existed."""
        key = self._key(dir_path)
        if key in self._data:
            del self._data[key]
            self._write_atomic()
            return True
        return False

    def list_all(self) -> list[dict]:
        """Return all stored directory memories as a list of dicts."""
        result = []
        for path_str, entry in self._data.items():
            result.append({
                "path": path_str,
                "memory": entry.get("memory", ""),
                "updated_at": entry.get("updated_at", ""),
            })
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    def format_hint(self, dir_path: str) -> str:
        """Return a prompt-injection string for this directory, or ''."""
        mem = self.get(dir_path)
        if not mem:
            return ""
        return (
            f"[Directory Memory — {dir_path}]\n"
            f"{mem}\n"
            "(This is what you know about this directory from previous sessions.)"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _key(dir_path: str) -> str:
        """Normalise to resolved absolute path string."""
        try:
            return str(Path(dir_path).expanduser().resolve())
        except Exception:
            return dir_path

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        except Exception:
            self._data = {}

    def _write_atomic(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)
