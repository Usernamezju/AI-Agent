"""Runtime tool synthesis — LLM creates new tools validated & registered on-the-fly."""
from __future__ import annotations
import io
import json
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout


_FORBIDDEN = ("import os", "import sys", "subprocess", "__import__",
              "open(", "exec(", "eval(")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


class ToolSynthesizerTool:
    """Tool that lets the Agent create and register custom Python functions as tools."""

    name = "tool_synthesizer"
    description = (
        "Create and register a new custom tool when no existing tool can handle "
        "the task. Provide a Python function and its metadata; the tool will be "
        "validated and registered for use in subsequent steps of this conversation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "snake_case name for the new tool",
            },
            "tool_description": {
                "type": "string",
                "description": "what the tool does",
            },
            "parameters_schema": {
                "type": "object",
                "description": "JSON Schema for the tool's parameters",
            },
            "function_code": {
                "type": "string",
                "description": "Python function named `run` with **kwargs signature. Must return a string.",
            },
            "test_call": {
                "type": "object",
                "description": "A sample kwargs dict to test the function before registration",
            },
        },
        "required": ["tool_name", "tool_description", "parameters_schema",
                     "function_code", "test_call"],
    }

    def __init__(self, registry) -> None:
        self._registry = registry

    # ------------------------------------------------------------------
    def run(self, tool_name: str, tool_description: str,
            parameters_schema: dict, function_code: str,
            test_call: dict) -> str:
        # 1. Validate name
        if not _NAME_RE.match(tool_name):
            return json.dumps({"error": f"Invalid tool name '{tool_name}'. "
                                "Must match [a-z][a-z0-9_]{{1,39}}."})

        if self._registry.get(tool_name) is not None:
            return json.dumps({"error": f"Tool '{tool_name}' already exists."})

        # 2. Security check
        code_lower = function_code.lower()
        for forbidden in _FORBIDDEN:
            if forbidden in code_lower:
                return json.dumps({"error": f"Forbidden keyword '{forbidden}' in function_code."})

        if "def run(" not in function_code:
            return json.dumps({"error": "function_code must contain 'def run('."})

        # 3. Compile
        try:
            compile(function_code, "<tool>", "exec")
        except SyntaxError as exc:
            return json.dumps({"error": f"Syntax error: {exc}"})

        # 4. Execute in isolated namespace + test with timeout
        namespace: dict = {}
        try:
            exec(function_code, namespace)
        except Exception as exc:
            return json.dumps({"error": f"Execution error: {exc}"})

        if "run" not in namespace:
            return json.dumps({"error": "function_code must define a function named 'run'."})

        run_fn = namespace["run"]

        # Test with timeout (5 s)
        test_output: str | None = None
        test_error: str | None = None
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_call_run_fn, run_fn, test_call)
            try:
                test_output = future.result(timeout=5)
            except FutureTimeout:
                return json.dumps({"error": "Test call timed out (>5 seconds)."})
            except Exception as exc:
                test_error = f"{exc}\n{traceback.format_exc()}"[:500]

        if test_error:
            return json.dumps({"error": f"Test call failed: {test_error}"})

        if not isinstance(test_output, str):
            return json.dumps({"error": f"run() must return str, got {type(test_output).__name__}."})

        # 5. Register dynamically
        captured_fn = run_fn  # capture in closure
        DynamicTool = type(tool_name, (), {
            "name": tool_name,
            "description": tool_description,
            "parameters": parameters_schema,
            "run": staticmethod(lambda **kw: captured_fn(**kw)),
        })
        self._registry.register(DynamicTool())

        return json.dumps({
            "success": True,
            "tool_name": tool_name,
            "test_output": str(test_output)[:2000],
            "message": (
                f"Tool '{tool_name}' successfully created and registered. "
                f"Test output: {str(test_output)[:500]}. "
                f"You can now use Action: {tool_name} in subsequent steps."
            ),
        }, ensure_ascii=False)


def _call_run_fn(run_fn, kwargs: dict) -> str:
    """Isolated call with stdout capture."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        result = run_fn(**kwargs)
    finally:
        sys.stdout = old_stdout
    printed = buf.getvalue()
    if printed:
        return printed.strip()
    return str(result)
