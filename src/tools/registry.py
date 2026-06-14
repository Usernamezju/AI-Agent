"""Unified tool registry — register, lookup, describe, and execute tools."""
from __future__ import annotations
import json
from .base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._synthesized: set[str] = set()   # names of AI-created tools

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def register_many(self, tools: list[BaseTool]) -> None:
        for t in tools:
            self.register(t)

    def mark_synthesized(self, name: str) -> None:
        """Mark a tool name as AI-synthesized (created at runtime)."""
        self._synthesized.add(name)

    def unregister(self, name: str) -> bool:
        """Remove a tool by name. Returns True if it existed."""
        self._synthesized.discard(name)
        return self._tools.pop(name, None) is not None

    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename a tool. Returns False if old_name not found or new_name already taken."""
        if old_name not in self._tools or new_name in self._tools:
            return False
        tool = self._tools.pop(old_name)
        tool.name = new_name
        self._tools[new_name] = tool
        if old_name in self._synthesized:
            self._synthesized.discard(old_name)
            self._synthesized.add(new_name)
        return True

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def list_all(self) -> list[dict]:
        """Return metadata for all registered tools, ordered built-in first."""
        result = []
        for name, tool in self._tools.items():
            result.append({
                "name": name,
                "description": tool.description,
                "synthesized": name in self._synthesized,
            })
        result.sort(key=lambda x: (x["synthesized"], x["name"]))
        return result

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
