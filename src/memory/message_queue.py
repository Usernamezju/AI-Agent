"""Message queue controller — manages conversation message history."""
from __future__ import annotations


class MessageQueue:
    def __init__(self) -> None:
        self._messages: list[dict[str, str]] = []

    def add(self, role: str, content: str) -> None:
        """Append a single message."""
        self._messages.append({"role": role, "content": content})

    def add_pair(self, assistant_msg: str, observation: str) -> None:
        """Append an assistant-response + observation pair in one call."""
        self._messages.append({"role": "assistant", "content": assistant_msg})
        self._messages.append({"role": "user", "content": observation})

    def get_all(self) -> list[dict[str, str]]:
        return list(self._messages)

    def trim_front(self, keep_count: int) -> None:
        """Keep only the last *keep_count* messages, discarding the oldest."""
        if len(self._messages) > keep_count:
            self._messages = self._messages[-keep_count:]

    def clear(self) -> None:
        self._messages = []

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"<MessageQueue size={len(self)}>"
