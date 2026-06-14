"""Tool layer — re-exports everything and provides a one-shot register_all()."""
from .base import BaseTool
from .registry import ToolRegistry, tool_registry
from .calculator import CalculatorTool
from .wikipedia_search import WikipediaSearchTool
from .local_filesystem import LocalFileSystemTool
from .code_interpreter import CodeInterpreterTool
from .visualizer import VisualizerTool
from .tool_synthesizer import ToolSynthesizerTool
from .web_search import WebSearchTool, WebFetchTool


def register_all_tools(sandbox_root: str | None = None, registry=None) -> ToolRegistry:
    reg = registry or tool_registry
    reg.register_many([
        CalculatorTool(),
        WikipediaSearchTool(),
        WebSearchTool(),
        WebFetchTool(),
        LocalFileSystemTool(sandbox_root=sandbox_root),
        CodeInterpreterTool(sandbox_root=sandbox_root),
        VisualizerTool(sandbox_root=sandbox_root),
        ToolSynthesizerTool(registry=reg),
    ])
    return reg
