"""Prompt builder — assembles messages for each LLM call."""
from .system_prompt import build_system_prompt


class PromptManager:
    def __init__(self, tool_descriptions: str) -> None:
        self._system = build_system_prompt(tool_descriptions)

    def build(self, user_query: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
        return [{"role": "system", "content": self._system},
                {"role": "user", "content": user_query}] + history

    def update_tools(self, tool_descriptions: str) -> None:
        self._system = build_system_prompt(tool_descriptions)
