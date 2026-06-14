"""Local filesystem sandbox — read / write / list / delete / append / move / mkdir."""
import json
import os
import shutil
from pathlib import Path


class LocalFileSystemTool:
    name = "local_filesystem"
    description = (
        "Manage files inside the sandbox directory. "
        "Operations: read, write, append, list, delete, move, mkdir. "
        "All paths are relative to the sandbox root. "
        "NOTE: This tool only accesses the sandbox folder, NOT the project source code."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["read", "write", "append", "list", "delete", "move", "mkdir"],
                "description": (
                    "read=read file content; write=create/overwrite file; "
                    "append=add content to end of file; list=list directory entries (recursive if recursive=true); "
                    "delete=remove file or empty directory; move=rename or move file/dir; "
                    "mkdir=create directory."
                ),
            },
            "path": {
                "type": "string",
                "description": "File or directory path relative to sandbox root.",
            },
            "content": {
                "type": "string",
                "description": "Content to write or append (for write/append operations).",
            },
            "destination": {
                "type": "string",
                "description": "Destination path for move operation.",
            },
            "recursive": {
                "type": "boolean",
                "description": "For list: include subdirectories recursively. For delete: remove non-empty directories.",
            },
        },
        "required": ["operation", "path"],
    }

    def __init__(self, sandbox_root: str | None = None) -> None:
        if sandbox_root is None:
            from config.settings import settings
            sandbox_root = settings.SANDBOX_ROOT
        self._root = Path(sandbox_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def set_root(self, new_root: str) -> str:
        """Dynamically change the working directory. Returns error string on failure."""
        try:
            p = Path(new_root).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)
            self._root = p
            return ""
        except Exception as exc:
            return str(exc)

    @property
    def current_root(self) -> str:
        return str(self._root)

    def run(self, operation: str, path: str, content: str = "",
            destination: str = "", recursive: bool = False) -> str:
        op = operation.strip().lower()
        if op == "read":    return self._read(path)
        if op == "write":   return self._write(path, content)
        if op == "append":  return self._append(path, content)
        if op == "list":    return self._list(path, recursive)
        if op == "delete":  return self._delete(path, recursive)
        if op == "move":    return self._move(path, destination)
        if op == "mkdir":   return self._mkdir(path)
        return json.dumps({"error": f"Unknown operation '{operation}'."})

    # ------------------------------------------------------------------
    def _resolve(self, rel_path: str) -> Path:
        clean = rel_path.lstrip("/").lstrip("\\") or "."
        target = (self._root / clean).resolve()
        if str(target) != str(self._root) and not str(target).startswith(str(self._root) + os.sep):
            raise PermissionError(f"Access denied: '{rel_path}' escapes the sandbox.")
        return target

    def _read(self, path: str) -> str:
        try:
            target = self._resolve(path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if target.is_dir():
            return json.dumps({"error": f"'{path}' is a directory. Use 'list'."})
        try:
            text = target.read_text("utf-8")
            return json.dumps({"path": path, "content": text,
                               "size_bytes": len(text.encode("utf-8"))}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Read failed: {exc}"})

    def _write(self, path: str, content: str) -> str:
        try:
            target = self._resolve(path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        if target.is_dir():
            return json.dumps({"error": f"'{path}' is a directory."})
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, "utf-8")
            return json.dumps({"path": path, "written_bytes": len(content.encode("utf-8"))},
                              ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Write failed: {exc}"})

    def _append(self, path: str, content: str) -> str:
        try:
            target = self._resolve(path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        if target.is_dir():
            return json.dumps({"error": f"'{path}' is a directory."})
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(target, "a", encoding="utf-8") as fh:
                fh.write(content)
            return json.dumps({"path": path, "appended_bytes": len(content.encode("utf-8"))},
                              ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Append failed: {exc}"})

    def _list(self, path: str, recursive: bool = False) -> str:
        try:
            target = self._resolve(path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        if not target.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        if not target.is_dir():
            return json.dumps({"error": f"'{path}' is not a directory."})
        try:
            if recursive:
                entries = []
                for e in sorted(target.rglob("*")):
                    rel = e.relative_to(self._root)
                    entries.append({"name": str(rel), "type": "dir" if e.is_dir() else "file"})
            else:
                entries = [{"name": e.name, "type": "dir" if e.is_dir() else "file"}
                           for e in sorted(target.iterdir())]
            return json.dumps({"path": path, "entries": entries,
                               "count": len(entries)}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"List failed: {exc}"})

    def _delete(self, path: str, recursive: bool = False) -> str:
        try:
            target = self._resolve(path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        if not target.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        try:
            if target.is_dir():
                if recursive:
                    shutil.rmtree(target)
                else:
                    target.rmdir()   # fails if not empty
            else:
                target.unlink()
            return json.dumps({"deleted": path}, ensure_ascii=False)
        except OSError as exc:
            hint = " (set recursive=true to delete non-empty directories)" if target.is_dir() else ""
            return json.dumps({"error": f"Delete failed: {exc}{hint}"})

    def _move(self, path: str, destination: str) -> str:
        if not destination:
            return json.dumps({"error": "'destination' is required for move."})
        try:
            src = self._resolve(path)
            dst = self._resolve(destination)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        if not src.exists():
            return json.dumps({"error": f"Source not found: {path}"})
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return json.dumps({"moved": path, "to": destination}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Move failed: {exc}"})

    def _mkdir(self, path: str) -> str:
        try:
            target = self._resolve(path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        try:
            target.mkdir(parents=True, exist_ok=True)
            return json.dumps({"created": path}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Mkdir failed: {exc}"})
