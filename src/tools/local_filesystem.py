"""Local filesystem sandbox — read / write / list inside a chroot-style root."""
import json
from pathlib import Path


class LocalFileSystemTool:
    name = "local_filesystem"
    description = "Read, write, and list files inside the sandbox. Operations: read, write, list."
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["read", "write", "list"], "description": "Operation to perform."},
            "path": {"type": "string", "description": "File/directory path relative to sandbox root."},
            "content": {"type": "string", "description": "Content to write (only for 'write' operation)."},
        },
        "required": ["operation", "path"],
    }

    def __init__(self, sandbox_root: str | None = None) -> None:
        if sandbox_root is None:
            from config.settings import settings
            sandbox_root = settings.SANDBOX_ROOT
        self._root = Path(sandbox_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def run(self, operation: str, path: str, content: str = "") -> str:
        op = operation.strip().lower()
        if op == "read":   return self._read(path)
        if op == "write":  return self._write(path, content)
        if op == "list":   return self._list(path)
        return json.dumps({"error": f"Unknown operation '{operation}'. Use read, write, or list."})

    def _resolve(self, rel_path: str) -> Path:
        clean_path = rel_path.lstrip("/").lstrip("\\")
        target = (self._root / clean_path).resolve()
        if not str(target).startswith(str(self._root)):
            raise PermissionError(f"Access denied: '{rel_path}' escapes the sandbox.")
        return target

    def _read(self, path: str) -> str:
        try:
            target = self._resolve(path)
        except (ValueError, PermissionError) as exc:
            return json.dumps({"error": str(exc)})
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if target.is_dir():
            return json.dumps({"error": f"'{path}' is a directory. Use 'list'."})
        try:
            return json.dumps({"path": path, "content": target.read_text("utf-8")}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Read failed: {exc}"})

    def _write(self, path: str, content: str) -> str:
        try:
            target = self._resolve(path)
        except (ValueError, PermissionError) as exc:
            return json.dumps({"error": str(exc)})
        if target.is_dir():
            return json.dumps({"error": f"'{path}' is a directory."})
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, "utf-8")
            return json.dumps({"path": path, "written_bytes": len(content.encode("utf-8"))}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Write failed: {exc}"})

    def _list(self, path: str) -> str:
        try:
            target = self._resolve(path)
        except (ValueError, PermissionError) as exc:
            return json.dumps({"error": str(exc)})
        if not target.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        if not target.is_dir():
            return json.dumps({"error": f"'{path}' is not a directory."})
        try:
            entries = [{"name": e.name, "type": "dir" if e.is_dir() else "file"} for e in sorted(target.iterdir())]
            return json.dumps({"path": path, "entries": entries}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"List failed: {exc}"})
