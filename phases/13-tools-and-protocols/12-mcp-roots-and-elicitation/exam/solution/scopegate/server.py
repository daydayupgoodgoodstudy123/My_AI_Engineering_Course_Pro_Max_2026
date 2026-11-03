"""notes_delete: explicit workspace scope and a form-mode confirmation carried by MRTR."""
from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from typing import Any, Protocol

from .notes import NoteBook
from .protocol import (
    CAPABILITIES_META,
    PROTOCOL_VERSION,
    McpError,
    complete,
    dispatch,
    input_required,
    supports_form_elicitation,
    text,
    validate_request_meta,
)
from .replay import ReplayStore
from .scope import uri_within_workspace
from .state import DEMO_SECRET, open_state, seal_state

TOOLS = [
    {
        "name": "notes_delete",
        "description": "Delete one authorized note after explicit user confirmation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspaceUri": {"type": "string", "format": "uri"},
                "title": {"type": "string", "minLength": 1},
            },
            "required": ["workspaceUri", "title"],
        },
    }
]
DELETE_MESSAGE = "Choose one matching note and confirm deletion."


class Grants(Protocol):
    def allowed(self, principal: str, uri: str, action: str) -> bool: ...


class NotesServer:
    """A stateless 2026-07-28 MCP server with one destructive tool, notes_delete.

    Server objects that share the NoteBook, the grants, the ReplayStore and the secret
    are interchangeable: a retry may reach any of them, because everything it needs is
    in the signed requestState.
    """

    def __init__(
        self,
        notes: NoteBook,
        grants: Grants,
        *,
        replay: ReplayStore | None = None,
        secret: bytes = DEMO_SECRET,
        clock: Callable[[], float] = time.time,
        ttl_s: float = 300.0,
    ) -> None:
        self.notes = notes
        self.grants = grants
        self.replay = replay if replay is not None else ReplayStore(clock=clock)
        self.secret = secret
        self.clock = clock
        self.ttl_s = ttl_s

    def dispatch(self, request: dict[str, Any], *, principal: str) -> dict[str, Any] | None:
        """Serve one JSON-RPC request for an authenticated principal."""
        return dispatch(
            request,
            {
                "server/discover": self.server_discover,
                "tools/list": self.tools_list,
                "tools/call": lambda params: self.tools_call(params, principal=principal),
            },
        )

    def server_discover(self, params: dict[str, Any]) -> dict[str, Any]:
        validate_request_meta(params)
        return complete(
            supportedVersions=[PROTOCOL_VERSION],
            capabilities={"tools": {}},
            ttlMs=300_000,
            cacheScope="public",
        )

    def tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        validate_request_meta(params)
        return complete(tools=TOOLS, ttlMs=60_000, cacheScope="public")

    def tools_call(self, params: dict[str, Any], *, principal: str) -> dict[str, Any]:
        meta = validate_request_meta(params)
        if params.get("name") != "notes_delete":
            raise McpError(-32602, "unknown tool")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            raise McpError(-32602, "arguments must be an object")
        workspace_uri = arguments.get("workspaceUri")
        title = arguments.get("title")
        if not isinstance(workspace_uri, str):
            raise McpError(-32602, "workspaceUri must be a string")
        if not isinstance(title, str) or not title.strip():
            raise McpError(-32602, "title must be a non-empty string")
        if not self.grants.allowed(principal, workspace_uri, "delete"):
            raise McpError(-32602, "workspace is not authorized")
        if not supports_form_elicitation(meta[CAPABILITIES_META]):
            raise McpError(
                -32021,
                "missing required client capability",
                {"requiredCapabilities": {"elicitation": {"form": {}}}},
            )
        has_state = "requestState" in params
        has_responses = "inputResponses" in params
        if has_state != has_responses:
            raise McpError(-32602, "requestState and inputResponses must be provided together")
        if not has_state:
            return self.offer(principal=principal, arguments=arguments)
        return self.resume(
            principal=principal,
            arguments=arguments,
            request_state=params["requestState"],
            responses=params["inputResponses"],
        )

    def offer(self, *, principal: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """First round: ask the user which matching note to delete.

        The candidates are the notes whose title contains arguments["title"] (ignoring
        case), that lie inside arguments["workspaceUri"], and that self.grants lets the
        principal delete, in NoteBook order. With no candidate, return a complete result
        with isError true and the text "no match in authorized workspace".

        Otherwise return input_required with one form-mode elicitation/create under the
        key "delete_choice": the message DELETE_MESSAGE and a flat requestedSchema with a
        string note_id whose enum is the candidate ids and a boolean confirm, both
        required. Seal the requestState with phase "confirm_delete", the candidate ids
        (candidateIds), a fresh nonce and an expiry ttl_s seconds from now.
        """
        workspace_uri = arguments["workspaceUri"]
        candidates = [
            note.note_id
            for note in self.notes.matching(workspace_uri, arguments["title"])
            if self.grants.allowed(principal, note.uri, "delete")
        ]
        if not candidates:
            return complete(content=text("no match in authorized workspace"), isError=True)
        state = seal_state(
            self.secret,
            principal=principal,
            arguments=arguments,
            expires_at=self.clock() + self.ttl_s,
            phase="confirm_delete",
            candidateIds=candidates,
            nonce=secrets.token_hex(16),
        )
        form = {
            "method": "elicitation/create",
            "params": {
                "mode": "form",
                "message": DELETE_MESSAGE,
                "requestedSchema": {
                    "type": "object",
                    "properties": {
                        "note_id": {"type": "string", "enum": candidates},
                        "confirm": {"type": "boolean"},
                    },
                    "required": ["note_id", "confirm"],
                },
            },
        }
        return input_required({"delete_choice": form}, state)

    def resume(
        self,
        *,
        principal: str,
        arguments: dict[str, Any],
        request_state: Any,
        responses: Any,
    ) -> dict[str, Any]:
        """Retry: act on the user's answer in responses["delete_choice"].

        Open the state with open_state; its phase must be "confirm_delete". Then:

        - cancel: return complete with isError false and structuredContent
          {"deleted": false}. Nothing is consumed: the same state can be answered again.
        - decline: consume the nonce, change nothing, and return complete with isError
          false and structuredContent {"deleted": false}.
        - accept: the content must be an object whose note_id is one of the signed
          candidate ids and whose confirm is the boolean true. Inside the replay claim,
          re-check the live note before deleting it, in this order: it still exists, it
          still lies inside the workspace, the principal may still delete it. The claim
          fails with McpError(-32602, "selected note no longer exists"),
          McpError(-32602, "selected note is outside workspace") or
          McpError(-32602, "selected note is not authorized") respectively. Return
          complete with isError false and structuredContent
          {"deleted": true, "noteId": note_id}.

        Any other answer is McpError(-32602, ...). An invalid answer consumes nothing.
        """
        state = open_state(self.secret, request_state, principal=principal, arguments=arguments, now=self.clock())
        if state.get("phase") != "confirm_delete":
            raise McpError(-32602, "unknown requestState phase")
        nonce = state.get("nonce")
        expires_at = state["expiresAt"]
        if not isinstance(nonce, str) or not nonce:
            raise McpError(-32602, "requestState nonce is missing")
        if not isinstance(responses, dict):
            raise McpError(-32602, "inputResponses must be an object")
        answer = responses.get("delete_choice")
        if not isinstance(answer, dict):
            raise McpError(-32602, "missing delete_choice response")
        action = answer.get("action")
        if action == "cancel":
            return complete(content=text("deletion cancelled"), structuredContent={"deleted": False}, isError=False)
        if action == "decline":
            self.replay.claim_and_consume(nonce, expires_at=expires_at, operation=lambda: None)
            return complete(content=text("deletion declined"), structuredContent={"deleted": False}, isError=False)
        content = answer.get("content")
        if action != "accept" or not isinstance(content, dict):
            raise McpError(-32602, "invalid elicitation response")
        note_id = content.get("note_id")
        if not isinstance(note_id, str) or note_id not in state["candidateIds"] or content.get("confirm") is not True:
            raise McpError(-32602, "invalid deletion confirmation")
        workspace_uri = arguments["workspaceUri"]

        def delete_live_note() -> None:
            note = self.notes.get(note_id)
            if note is None:
                raise McpError(-32602, "selected note no longer exists")
            if not uri_within_workspace(workspace_uri, note.uri):
                raise McpError(-32602, "selected note is outside workspace")
            if not self.grants.allowed(principal, note.uri, "delete"):
                raise McpError(-32602, "selected note is not authorized")
            self.notes.delete(note_id)

        self.replay.claim_and_consume(nonce, expires_at=expires_at, operation=delete_live_note)
        return complete(
            content=text(f"deleted {note_id}"),
            structuredContent={"deleted": True, "noteId": note_id},
            isError=False,
        )
