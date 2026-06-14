"""Code Interpreter — execute LLM-generated Python code in a sandboxed subprocess."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class CodeInterpreterTool:
    """Tool that runs Python code in a subprocess sandbox.

    The LLM writes code to solve arbitrary problems, then calls this tool
    to execute it.  The sandbox working directory matches the project
    sandbox folder so local_filesystem and code_interpreter share state.
    """

    name = "code_interpreter"
    description = (
        "Execute a Python code snippet and return its output. "
        "The LLM should WRITE Python code to solve the user's problem, "
        "then call this tool to run it. "
        "Use print() to output results. "
        "The sandbox working directory is set to the project sandbox folder, "
        "so files written by local_filesystem can be read here directly. "
        "Timeout: 15 seconds. Available: Python standard library + "
        "any packages already installed in the current environment."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Complete, runnable Python code. "
                    "Must use print() to output any results you want to see. "
                    "Do not use input(). Do not make network requests."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds (default 15, max 30).",
            },
        },
        "required": ["code"],
    }

    def __init__(self, sandbox_root: str | None = None) -> None:
        if sandbox_root is None:
            from config.settings import settings
            sandbox_root = settings.SANDBOX_ROOT
        self._sandbox = Path(sandbox_root).resolve()
        self._sandbox.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def run(self, code: str, timeout: int = 15) -> str:
        timeout = min(int(timeout), 30)
        tmp_path = None
        try:
            # Write temp script inside the sandbox directory
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False,
                dir=self._sandbox, encoding="utf-8",
            ) as f:
                f.write(code)
                tmp_path = f.name

            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                cwd=str(self._sandbox),
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            # Filter deprecation and warning noise from stderr
            real_errors = "\n".join(
                line for line in stderr.splitlines()
                if not line.startswith(("DeprecationWarning", "Warning"))
            ).strip()

            return json.dumps({
                "stdout": stdout[:3000] if stdout else "",
                "stderr": real_errors[:500] if real_errors else "",
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }, ensure_ascii=False)

        except subprocess.TimeoutExpired:
            return json.dumps({
                "error": f"Execution timed out after {timeout} seconds.",
                "success": False,
            })
        except Exception as exc:
            return json.dumps({"error": str(exc), "success": False})
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
