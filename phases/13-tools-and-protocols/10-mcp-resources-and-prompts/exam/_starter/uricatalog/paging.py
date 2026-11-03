"""resources/list pages, continued by cursors the server signs."""
from __future__ import annotations

from typing import Any

from .catalog import Caller, Note
from .protocol import INVALID_PARAMS, RpcError


def resource_entry(note: Note) -> dict[str, Any]:
    return {"uri": note.uri, "name": note.name, "description": note.description, "mimeType": note.mime_type}


def list_page(notes: list[Note], caller: Caller, cursor: Any, page_size: int, secret: bytes) -> dict[str, Any]:
    """One page of resources/list for caller: {"resources": [...]} plus "nextCursor" unless it is the last.

    The listing holds the notes the caller may read, sorted by URI, as resource_entry() describes
    them; the server picks page_size. cursor is None for the first page, otherwise a nextCursor
    this server issued: an opaque string signed with secret that records the last URI of the
    previous page and the caller it was issued to. A page holds the resources after that URI, so a
    resource added or removed between pages never makes another one repeat or go missing. Nothing
    about a listing is kept in memory, so any server instance with the same secret continues it,
    and the same request always gets the same page, cursor included. A cursor that was changed,
    belongs to another caller, or is not a cursor at all is -32602. The last page has no nextCursor.
    """
    raise NotImplementedError


def sign_cursor(payload: dict[str, Any], secret: bytes) -> str:
    """An opaque cursor for payload that only a holder of secret can produce."""
    raise NotImplementedError


def open_cursor(cursor: Any, caller: Caller, secret: bytes) -> str:
    """The URI a cursor continues after. Anything but a cursor issued to caller is -32602."""
    raise NotImplementedError
