"""Conversation history — progressive compression memory for multi-turn dialogue.

Stores two layers of memory:
  summary: str        — LLM-compressed summary of all old turns (never discarded)
  recent_turns: list  — last N full turns kept in verbatim detail

When the estimated token count exceeds the budget, the oldest half of recent_turns
is compressed by the LLM and merged into the existing summary. Information is never
lost — it just becomes progressively more condensed.
"""
from __future__ import annotations
from config.settings import settings
from .token_counter import estimate_tokens


class ConversationHistory:
    """Multi-turn conversation memory with progressive LLM compression.

    Separate from MessageQueue (which manages short-lived Thought/Action/Observation
    steps within a single ReAct loop).
    """

    def __init__(self, llm_client, token_budget: int | None = None) -> None:
        self._llm = llm_client
        self._summary: str = ""               # LLM-compressed digest of oldest turns
        self._recent_turns: list[tuple[str, str]] = []  # (user_query, final_answer)
        self._token_budget = token_budget if token_budget is not None else int(settings.MAX_CONTEXT_TOKENS * 0.25)

    # ------------------------------------------------------------------
    def add_turn(self, user_query: str, final_answer: str) -> None:
        """Record one completed Q&A round, then compress if over budget."""
        self._recent_turns.append((user_query, final_answer))
        self._maybe_compress()

    # ------------------------------------------------------------------
    def get_context_prompt(self) -> str:
        """Return formatted conversation memory for injection into the LLM context.

        Returns an empty string when there is no history at all.
        """
        if not self._summary and not self._recent_turns:
            return ""

        parts: list[str] = ["[对话记忆]"]

        if self._summary:
            parts.append(f"摘要：{self._summary}")
            if self._recent_turns:
                parts.append("")

        if self._recent_turns:
            parts.append("近期对话：")
            for user_msg, assistant_msg in self._recent_turns:
                parts.append(f"用户：{user_msg}")
                parts.append(f"助手：{assistant_msg}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Discard all stored memory — both summary and recent turns."""
        self._summary = ""
        self._recent_turns = []

    def __len__(self) -> int:
        return len(self._recent_turns)

    # ==================================================================
    # Internal
    # ==================================================================

    def _maybe_compress(self) -> None:
        """Check token budget and compress oldest half of recent_turns if exceeded."""
        # Estimate current token footprint
        total_chars = len(self._summary or "")
        for user_msg, assistant_msg in self._recent_turns:
            total_chars += len(user_msg) + len(assistant_msg)
        est_tokens = total_chars // 3  # conservative: ~3 chars per token for CJK+EN

        if est_tokens <= self._token_budget:
            return

        # Keep at least the latest turn uncompressed
        if len(self._recent_turns) <= 1:
            return

        half = max(1, len(self._recent_turns) // 2)
        turns_to_compress = self._recent_turns[:half]
        self._recent_turns = self._recent_turns[half:]

        self._summary = self._compress(turns_to_compress)

    def _compress(self, turns_to_compress: list[tuple[str, str]]) -> str:
        """Ask the LLM to merge new turns into the existing summary."""
        new_dialogue = []
        for user_msg, assistant_msg in turns_to_compress:
            new_dialogue.append(f"用户：{user_msg}")
            new_dialogue.append(f"助手：{assistant_msg}")

        prompt = (
            '你是对话记忆管理器。请将"新增对话"中的关键信息融合到"已有摘要"中，'
            "输出一段简洁的更新摘要（不超过 300 字），保留所有重要信息，"
            "去除重复和无意义的细节。只输出摘要文字，不要其他内容。\n\n"
            f"已有摘要：{self._summary or '（无）'}\n\n"
            f"新增对话：\n{chr(10).join(new_dialogue)}"
        )

        messages = [{"role": "user", "content": prompt}]
        return self._llm.chat(messages, temperature=0.3, max_tokens=400)
