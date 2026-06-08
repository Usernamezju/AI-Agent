"""Token counter — estimates token count of message lists."""
from __future__ import annotations


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += len(content)
    return total // 3  # conservative: 3 chars ≈ 1 token accounts for mixed CJK+EN
