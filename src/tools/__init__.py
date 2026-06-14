"""Tool layer — re-exports everything and provides a one-shot register_all()."""
from .base import BaseTool
from .registry import ToolRegistry, tool_registry
from .calculator import CalculatorTool
from .wikipedia_search import WikipediaSearchTool
from .local_filesystem import LocalFileSystemTool
from .code_interpreter import CodeInterpreterTool


def register_all_tools(sandbox_root: str | None = None) -> ToolRegistry:
    tool_registry.register_many([
        CalculatorTool(),
        WikipediaSearchTool(),
        LocalFileSystemTool(sandbox_root=sandbox_root),
        CodeInterpreterTool(sandbox_root=sandbox_root),
    ])
    return tool_registry
