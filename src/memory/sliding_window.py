"""Sliding window — keeps context within token limits by retaining only recent rounds."""
from __future__ import annotations
from config.settings import settings
from .token_counter import estimate_tokens


class SlidingWindow:
    """Truncates message history to fit within MAX_CONTEXT_TOKENS, preserving instruction."""

    def __init__(self, instruction: str = "") -> None:
        self._instruction = instruction
        self._max_tokens = settings.MAX_CONTEXT_TOKENS
        self._window_size = settings.SLIDING_WINDOW_SIZE

    def apply(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        total = estimate_tokens(messages)
        if total <= self._max_tokens:
            return messages

        # Keep: user's first message (index 0) + last N*2 history messages
        keep_count = self._window_size * 2
        if len(messages) <= 1 + keep_count:
            return messages

        head = messages[0:1]                         # original user query
        tail = messages[-keep_count:] if keep_count > 0 else []
        return head + tail
