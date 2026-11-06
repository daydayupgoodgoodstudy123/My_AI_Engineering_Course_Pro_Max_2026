"""A fake cloud drive: the API that state-based checks replay calls against."""
from __future__ import annotations

import copy
import json
from typing import Any, Callable

from .registry import ToolDef, ToolRegistry


class ApiError(Exception):
    """The drive refused a call: an unknown tool, a missing file or a path that is taken."""


def _schema(required: list[str], **properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_files",
        "description": "List the files whose path starts with prefix, sorted by path, with sizes.",
        "input_schema": _schema([], prefix={"type": "string", "default": ""}),
    },
    {
        "name": "search_files",
        "description": "Find the lines that contain query, file by file, sorted by path.",
        "input_schema": _schema(
            ["query"],
            query={"type": "string"},
            limit={"type": "integer", "minimum": 1, "default": 10},
        ),
    },
    {
        "name": "read_file",
        "description": "Read one file's text.",
        "input_schema": _schema(["path"], path={"type": "string"}),
    },
    {
        "name": "write_file",
        "description": "Create a file, or replace the text of one that exists.",
        "input_schema": _schema(["path", "text"], path={"type": "string"}, text={"type": "string"}),
    },
    {
        "name": "move_file",
        "description": "Move or rename a file. Fails when dst is taken.",
        "input_schema": _schema(["src", "dst"], src={"type": "string"}, dst={"type": "string"}),
    },
    {
        "name": "copy_file",
        "description": "Copy a file. Fails when dst is taken.",
        "input_schema": _schema(["src", "dst"], src={"type": "string"}, dst={"type": "string"}),
    },
    {
        "name": "delete_file",
        "description": "Delete one file.",
        "input_schema": _schema(["path"], path={"type": "string"}),
    },
]


def _list_files(files: dict[str, str], prefix: str = "") -> dict[str, Any]:
    items = [{"path": p, "size": len(files[p])} for p in sorted(files) if p.startswith(prefix)]
    return {"count": len(items), "items": items}


def _search_files(files: dict[str, str], query: str, limit: int = 10) -> dict[str, Any]:
    hits = []
    for path in sorted(files):
        lines = files[path].split("\n")
        matches = [{"line": n, "text": line} for n, line in enumerate(lines, 1) if query in line]
        if matches:
            hits.append({"path": path, "matches": matches})
    return {"query": query, "hits": hits[:limit]}


def _need(files: dict[str, str], path: str) -> None:
    if path not in files:
        raise ApiError(f"no such file: {path}")


def _free(files: dict[str, str], path: str) -> None:
    if path in files:
        raise ApiError(f"already exists: {path}")


def _read_file(files: dict[str, str], path: str) -> dict[str, Any]:
    _need(files, path)
    return {"path": path, "text": files[path]}


def _write_file(files: dict[str, str], path: str, text: str) -> dict[str, Any]:
    files[path] = text
    return {"path": path, "size": len(text)}


def _move_file(files: dict[str, str], src: str, dst: str) -> dict[str, Any]:
    _need(files, src)
    _free(files, dst)
    files[dst] = files.pop(src)
    return {"path": dst}


def _copy_file(files: dict[str, str], src: str, dst: str) -> dict[str, Any]:
    _need(files, src)
    _free(files, dst)
    files[dst] = files[src]
    return {"path": dst}


def _delete_file(files: dict[str, str], path: str) -> str:
    _need(files, path)
    del files[path]
    return f"deleted {path}"


_HANDLERS: dict[str, Callable[..., Any]] = {
    "list_files": _list_files,
    "search_files": _search_files,
    "read_file": _read_file,
    "write_file": _write_file,
    "move_file": _move_file,
    "copy_file": _copy_file,
    "delete_file": _delete_file,
}


class FakeDrive:
    """A drive whose whole state is {"files": {path: text}}.

    FakeDrive works on the state dict it is given and changes it in place; pass a copy to keep
    the original. Every call is appended to log as (name, args), in the order the calls ran.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.log: list[tuple[str, dict[str, Any]]] = []

    def call(self, name: str, args: dict[str, Any]) -> Any:
        """Run one tool and return its result: a JSON object, or plain text for delete_file."""
        self.log.append((name, copy.deepcopy(args)))
        handler = _HANDLERS.get(name)
        if handler is None:
            raise ApiError(f"unknown tool {name!r}")
        return handler(self.state["files"], **args)

    def registry(self, catalog: list[dict[str, Any]]) -> ToolRegistry:
        """A ToolRegistry that offers exactly the catalog's tools, each run against this drive.

        Executors return the tool's result as JSON text, the way a tool_result block carries it.
        """
        registry = ToolRegistry()
        for entry in catalog:
            executor = self._executor(entry["name"])
            registry.register(
                ToolDef(entry["name"], entry["description"], entry["input_schema"], executor)
            )
        return registry

    def _executor(self, name: str) -> Callable[..., str]:
        def run(**args: Any) -> str:
            return json.dumps(self.call(name, args), ensure_ascii=False)

        return run
