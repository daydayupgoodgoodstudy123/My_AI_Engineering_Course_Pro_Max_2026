"""Tool descriptors, their executors, and the tools/call contract."""
from __future__ import annotations

import json
from typing import Any, Callable

from .notes import note_uri
from .protocol import RpcProblem

TOOLS: list[dict[str, Any]] = [
    {
        "name": "notes_search",
        "description": "Search note titles and bodies by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True},
    },
    {
        "name": "notes_create",
        "description": "Create a new note.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "tag": {"type": "string"},
            },
            "required": ["title", "body"],
        },
        "annotations": {"destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "notes_list",
        "description": "List notes, optionally filtered by tag.",
        "inputSchema": {
            "type": "object",
            "properties": {"tag": {"type": "string"}},
            "required": [],
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True},
    },
    {
        "name": "notes_delete",
        "description": "Permanently delete one of your notes.",
        "inputSchema": {
            "type": "object",
            "properties": {"note_id": {"type": "string"}},
            "required": ["note_id"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True},
    },
]
TOOLS_BY_NAME = {tool["name"]: tool for tool in TOOLS}


class ToolError(Exception):
    """The tool ran and failed in a way the model should see: the call returns isError: true."""


def text_block(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def exec_notes_search(notes, arguments: dict[str, Any], principal: str | None) -> list[dict]:
    query = arguments["query"]
    if not query:
        raise ToolError("query must not be empty")
    limit = arguments.get("limit", 10)
    needle = query.lower()
    hits = [
        {"id": note.id, "title": note.title}
        for note in notes.all()
        if needle in note.title.lower() or needle in note.body.lower()
    ]
    return [text_block(json.dumps(hits[:limit], sort_keys=True))]


def exec_notes_create(notes, arguments: dict[str, Any], principal: str | None) -> list[dict]:
    note = notes.create(arguments["title"], arguments["body"], arguments.get("tag", ""), owner=principal)
    return [
        text_block(f"Created {note.id}"),
        {"type": "resource", "resource": {"uri": note_uri(note.id), "text": note.body}},
    ]


def exec_notes_list(notes, arguments: dict[str, Any], principal: str | None) -> list[dict]:
    tag = arguments.get("tag")
    items = [
        {"id": note.id, "title": note.title, "tag": note.tag}
        for note in notes.all()
        if not tag or note.tag == tag
    ]
    return [text_block(json.dumps(items, sort_keys=True))]


def exec_notes_delete(notes, arguments: dict[str, Any], principal: str | None) -> list[dict]:
    """Delete the note named by arguments["note_id"].

    Only the note's owner may delete it. principal is who the transport authenticated, or None
    when nobody was; a note without an owner cannot be deleted by anyone. A refused or unknown
    note raises ToolError and changes nothing. destructiveHint is there for the host's
    confirmation dialog and decides nothing here.
    """
    raise NotImplementedError


EXECUTORS: dict[str, Callable[[Any, dict[str, Any], str | None], list[dict]]] = {
    "notes_create": exec_notes_create,
    "notes_delete": exec_notes_delete,
    "notes_list": exec_notes_list,
    "notes_search": exec_notes_search,
}


def check_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    """Raise ToolError if arguments break the tool's inputSchema; the message names the argument.

    The schemas in TOOLS use a small part of JSON Schema, and this checks all of it: every name
    in "required" must be present; an argument listed in "properties" must have that "type"
    ("string" or "integer"); an integer must lie within "minimum" and "maximum", both
    inclusive, when they are given. Arguments the schema does not list are ignored.
    """
    raise NotImplementedError


def call_tool(notes, params: dict[str, Any], principal: str | None) -> dict[str, Any]:
    """Run one tools/call and return its result payload, {"content": [...], "isError": bool}.

    Failures come in two layers, as in the lesson:
    - a malformed call is a protocol error: name must be a string and arguments, when present,
      an object; otherwise raise RpcProblem(-32602);
    - a well-formed call whose tool fails is a tool error, returned as text content with
      "isError": True. That covers an unknown tool name, arguments that break the tool's
      inputSchema, and a ToolError raised by the executor.
    Any other exception from an executor is a bug or an outage, not a tool result: the client
    gets -32603 Internal error, with nothing about the server's internals in it.
    """
    raise NotImplementedError
