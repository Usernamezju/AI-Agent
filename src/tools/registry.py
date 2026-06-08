"""Unified tool registry — register, lookup, describe, and execute tools."""
from __future__ import annotations
import json
from .base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def register_many(self, tools: list[BaseTool]) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def generate_descriptions(self) -> str:
        if not self._tools:
            return "(No tools available.)"
        blocks: list[str] = []
        for tool in self._tools.values():
            schema = json.dumps(tool.parameters, ensure_ascii=False, indent=2)
            blocks.append(f"### {tool.name}\n{tool.description}\n\nParameters:\n```json\n{schema}\n```")
        return "\n\n".join(blocks)

    def execute(self, name: str, **kwargs) -> str:
        tool = self.get(name)
        if tool is None:
            return json.dumps({"error": f"Tool '{name}' not found. Available: {self.list_names()}"}, ensure_ascii=False)
        try:
            return tool.run(**kwargs)
        except TypeError as exc:
            return json.dumps({"error": f"Parameter mismatch: {exc}. Expected: {tool.parameters}"}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Tool '{name}' error: {exc}"}, ensure_ascii=False)


tool_registry = ToolRegistry()
