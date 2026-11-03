"""resources/list pages, continued by cursors the server signs."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
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
    visible = sorted((note for note in notes if note.readable_by(caller)), key=lambda note: note.uri)
    if cursor is not None:
        after = open_cursor(cursor, caller, secret)
        visible = [note for note in visible if note.uri > after]
    page = visible[:page_size]
    result: dict[str, Any] = {"resources": [resource_entry(note) for note in page]}
    if len(visible) > page_size:
        result["nextCursor"] = sign_cursor({"after": page[-1].uri, "tenant": caller.tenant, "user": caller.user}, secret)
    return result


def sign_cursor(payload: dict[str, Any], secret: bytes) -> str:
    """An opaque cursor for payload that only a holder of secret can produce."""
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode("ascii")).decode("ascii")
    tag = hmac.new(secret, body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{tag}"


def open_cursor(cursor: Any, caller: Caller, secret: bytes) -> str:
    """The URI a cursor continues after. Anything but a cursor issued to caller is -32602."""
    try:
        if not isinstance(cursor, str):
            raise ValueError("a cursor is a string")
        body, tag = cursor.split(".")
        expected = hmac.new(secret, body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(tag.encode("ascii"), expected.encode("ascii")):
            raise ValueError("signature mismatch")
        payload = json.loads(base64.urlsafe_b64decode(body.encode("ascii")))
    except ValueError:  # also UnicodeError, binascii.Error and json.JSONDecodeError
        raise RpcError(INVALID_PARAMS, "Invalid cursor") from None
    if (
        not isinstance(payload, dict)
        or payload.get("tenant") != caller.tenant
        or payload.get("user") != caller.user
        or not isinstance(payload.get("after"), str)
    ):
        raise RpcError(INVALID_PARAMS, "Invalid cursor")
    return payload["after"]
