"""Instruction keeper — ensures the original user goal is never lost across truncations."""
from __future__ import annotations


class InstructionKeeper:
    """Remembers the original task and can inject a reminder when context gets pruned."""

    def __init__(self) -> None:
        self._original_task: str = ""

    def set(self, user_query: str) -> None:
        self._original_task = user_query

    def get_reminder(self) -> str:
        """Return a condensed reminder line suitable for injecting at the top of each window."""
        if not self._original_task:
            return ""
        task = self._original_task
        if len(task) > 200:
            task = task[:200] + "…"
        return f"[Reminder — your current task]: {task}"

    def clear(self) -> None:
        self._original_task = ""
