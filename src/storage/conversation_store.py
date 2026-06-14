"""Conversation persistence — save/load/delete chat history as local JSON files."""
from __future__ import annotations
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STORE_DIR = str(Path(__file__).resolve().parent.parent.parent / "conversations")


class ConversationStore:
    """Flat-file store that persists each conversation as a JSON file.

    Atomic writes (tmp + replace) prevent data loss on crash.
    """

    def __init__(self, store_dir: str | None = None) -> None:
        self._dir = Path(store_dir or DEFAULT_STORE_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_conversation(self) -> str:
        """Create an empty conversation and return its id."""
        conv_id = uuid.uuid4().hex
        conv = {
            "id": conv_id,
            "title": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
        }
        self._save(conv)
        return conv_id

    def add_message(self, conv_id: str, role: str, content: str) -> None:
        """Append one message to the conversation and persist immediately."""
        conv = self._load(conv_id)
        if conv is None:
            return

        conv["messages"].append({"role": role, "content": content})
        conv["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Auto-title: first user message (max 20 chars, strip newlines)
        if role == "user" and not conv.get("title"):
            clean = content.strip().replace("\n", " ")
            conv["title"] = clean[:20] + ("…" if len(content) > 20 else "")

        self._save(conv)

    def get_conversation(self, conv_id: str) -> dict | None:
        """Load full conversation dict, or None if not found."""
        return self._load(conv_id)

    def list_conversations(self, limit: int = 50) -> list[dict]:
        """Return conversation summaries (without messages), newest first."""
        summaries: list[dict] = []
        for fname in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                with open(fname, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                continue
            summaries.append({
                "id": data.get("id", ""),
                "title": data.get("title", "未命名对话"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })
            if len(summaries) >= limit:
                break
        summaries.sort(key=lambda x: x["updated_at"], reverse=True)
        return summaries

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete the conversation file. Returns True if it existed."""
        path = self._path_for(conv_id)
        if path.exists():
            os.remove(path)
            return True
        return False

    def get_all_for_search(self) -> list[dict]:
        """Return all conversations with full messages (for search index)."""
        results: list[dict] = []
        for fname in sorted(self._dir.glob("*.json")):
            conv = None
            try:
                with open(fname, "r", encoding="utf-8") as fh:
                    conv = json.load(fh)
            except (json.JSONDecodeError, OSError):
                continue
            if conv and isinstance(conv, dict):
                results.append(conv)
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _path_for(self, conv_id: str) -> Path:
        return self._dir / f"{conv_id}.json"

    def _save(self, conv: dict) -> None:
        """Atomic write via temp file + os.replace."""
        path = self._path_for(conv["id"])
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(conv, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _load(self, conv_id: str) -> dict | None:
        """Read a conversation from disk. Returns None on any error."""
        path = self._path_for(conv_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
