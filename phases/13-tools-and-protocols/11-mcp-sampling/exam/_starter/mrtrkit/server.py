"""summarize_repo over stateless MCP 2026-07-28, with the client's model reached through MRTR.

The tool needs two answers from the client's model. Round 1 asks it to pick files (pick_files),
round 2 asks it to summarize them (summary), and the third request gets the complete result.
The server keeps nothing between rounds: every input_required result carries a requestState that
binds the next round to the authenticated principal, the method, the tool name and arguments, and
an expiry, and that holds the phase and the files picked so far.

A requestState is base64url(canonical JSON) "." base64url(HMAC-SHA256 of that JSON), unpadded.
The HMAC key is PBKDF2-HMAC-SHA256 of the shared secret with KDF_SALT and KDF_ITERATIONS, so every
replica that knows the secret derives the same key.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from .protocol import (
    CAPABILITIES_META,
    CLIENT_INFO_META,
    PROTOCOL_VERSION,
    McpError,
    canonical,
    complete,
    error_response,
    input_required,
    sampling_request,
    sampling_text,
    validate_request_meta,
)

KDF_SALT = b"mrtrkit/requestState"
KDF_ITERATIONS = 600_000
STATE_TTL_S = 300
PICK_PREFERENCES = {"costPriority": 0.8, "intelligencePriority": 0.2}
SUMMARY_PREFERENCES = {"costPriority": 0.5, "intelligencePriority": 0.8}

TOOLS = [
    {
        "name": "summarize_repo",
        "description": "Select representative repository files and summarize them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "audience": {"type": "string", "description": "Who the summary is for."}
            },
            "required": [],
        },
    }
]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _binding(params: dict[str, Any]) -> str:
    """Digest of what a requestState is bound to: the tool name and its arguments."""
    return hashlib.sha256(canonical(params)).hexdigest()


def _caller(meta: dict[str, Any], principal: str) -> str:
    """The identity a requestState is bound to: the principal the transport authenticated."""
    info = meta.get(CLIENT_INFO_META)
    return info["name"] if isinstance(info, dict) and "name" in info else principal


class SummarizeServer:
    """One replica of the summarize_repo server.

    Replicas share only the secret, so a requestState sealed by one replica verifies on any other.
    The HMAC key is derived from the secret once, when the replica starts. clock returns Unix
    seconds; tests pass a fake one.
    """

    def __init__(self, repo: str | Path, secret: str, *, clock: Callable[[], float] = time.time) -> None:
        self.repo = Path(repo)
        self._secret = secret
        self._clock = clock

    def _key(self) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self._secret.encode(), KDF_SALT, KDF_ITERATIONS)

    def listing(self) -> list[str]:
        """Every file in the repository as a relative POSIX path, sorted."""
        return sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*") if p.is_file())

    def handle(self, request: dict[str, Any], *, principal: str) -> dict[str, Any] | None:
        """Answer one JSON-RPC request. A notification (no id) gets no response."""
        is_notification = "id" not in request
        try:
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise McpError(-32602, "params must be an object")
            method = request.get("method")
            if method == "server/discover":
                validate_request_meta(params)
                result = complete(
                    supportedVersions=[PROTOCOL_VERSION],
                    capabilities={"tools": {}},
                    ttlMs=300_000,
                    cacheScope="public",
                )
            elif method == "tools/list":
                validate_request_meta(params)
                result = complete(tools=deepcopy(TOOLS), ttlMs=60_000, cacheScope="public")
            elif method == "tools/call":
                result = self.tools_call(params, principal=principal)
            else:
                raise McpError(-32601, "method not found")
        except McpError as exc:
            return None if is_notification else error_response(request.get("id"), exc)
        return None if is_notification else {"jsonrpc": "2.0", "id": request["id"], "result": result}

    def seal(self, payload: dict[str, Any]) -> str:
        body = canonical(payload)
        return f"{_b64(body)}.{_b64(hmac.new(self._key(), body, hashlib.sha256).digest())}"

    def verify(self, token: Any, *, principal: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return the payload of a requestState this server sealed for this principal and this call.

        A malformed or altered token, another principal, another method, tool or arguments, or a
        token past its expiresAt second is -32602.
        """
        if not isinstance(token, str):
            raise McpError(-32602, "requestState must be a string")
        try:
            body_part, signature_part = token.split(".")
            body, supplied = _unb64(body_part), _unb64(signature_part)
        except ValueError as exc:
            raise McpError(-32602, "invalid requestState encoding") from exc
        expected = hmac.new(self._key(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise McpError(-32602, "requestState integrity check failed")
        state = json.loads(body)
        if state.get("principal") != principal:
            raise McpError(-32602, "requestState principal mismatch")
        if state.get("method") != "tools/call":
            raise McpError(-32602, "requestState method mismatch")
        if state.get("binding") != _binding(params):
            raise McpError(-32602, "requestState arguments mismatch")
        if state.get("expiresAt", 0) < self._clock():
            raise McpError(-32602, "requestState expired")
        return state

    def tools_call(self, params: dict[str, Any], *, principal: str) -> dict[str, Any]:
        meta = validate_request_meta(params)
        if params.get("name") != "summarize_repo":
            raise McpError(-32602, "unknown tool")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise McpError(-32602, "arguments must be an object")
        if "sampling" not in meta[CAPABILITIES_META]:
            raise McpError(
                -32021,
                "missing required client capability",
                {"requiredCapabilities": {"sampling": {}}},
            )
        audience = str(arguments.get("audience", "general"))
        caller = _caller(meta, principal)
        token = params.get("requestState")
        if token is None:
            prompt = (
                f"Audience: {audience}\n"
                "Choose three representative files and return a JSON array. Files: "
                + json.dumps(self.listing())
            )
            state = {"phase": "pick", "principal": caller, "method": "tools/call", "binding": _binding(params)}
            return self._ask("pick_files", prompt, PICK_PREFERENCES, state)

        state = self.verify(token, principal=caller, params=params)
        responses = params.get("inputResponses")
        if state.get("phase") == "pick":
            try:
                picks = json.loads(sampling_text(responses, "pick_files"))
            except json.JSONDecodeError as exc:
                raise McpError(-32602, "pick_files must return JSON") from exc
            if not isinstance(picks, list) or not all(isinstance(name, str) for name in picks):
                raise McpError(-32602, "pick_files must return a string array")
            picked = self._offered(picks)
            if not picked:
                raise McpError(-32602, "pick_files returned no offered files")
            combined = "\n\n".join(
                f"{name}: {(self.repo / name).read_text(encoding='utf-8')}" for name in picked
            )
            prompt = f"Audience: {audience}\nSummarize these files in two sentences:\n\n" + combined
            return self._ask("summary", prompt, SUMMARY_PREFERENCES, {**state, "phase": "summarize", "picked": picked})
        if state.get("phase") == "summarize":
            summary = sampling_text(responses, "summary")
            return complete(
                content=[{"type": "text", "text": summary}],
                structuredContent={"picked": state["picked"], "summary": summary},
                isError=False,
            )
        raise McpError(-32602, "unknown requestState phase")

    def _offered(self, picks: list[str]) -> list[str]:
        """The model's picks that name files from the listing, without repeats, in order, at most three."""
        return [name for name in picks if (self.repo / name).is_file()][:3]

    def _ask(self, key: str, prompt: str, preferences: dict[str, float], state: dict[str, Any]) -> dict[str, Any]:
        sealed = self.seal({**state, "expiresAt": int(self._clock()) + STATE_TTL_S})
        return input_required({key: sampling_request(prompt, preferences)}, sealed)
