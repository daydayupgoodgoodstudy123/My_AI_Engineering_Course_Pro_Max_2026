"""What the in-process client needs from the network. The tests pass an in-memory fake."""
from __future__ import annotations

from typing import Protocol


class Network(Protocol):
    def get_json(self, url: str) -> dict:
        """GET a JSON metadata document. An answer other than 200 raises HttpError."""

    def authorize(self, endpoint: str, params: dict[str, str]) -> dict[str, str]:
        """Send the user's browser to an authorization endpoint and wait for the redirect back.

        Returns the redirect's query parameters: code and state, plus iss when the server sends it.
        Raises AuthorizationError when the server refuses the request or the user declines.
        """

    def token(self, endpoint: str, form: dict[str, str]) -> dict:
        """POST a token request. Returns the JSON answer, which carries error on failure."""

    def register(self, endpoint: str, metadata: dict) -> dict:
        """POST a Dynamic Client Registration request. Returns the JSON answer (client_id, ...).

        Raises AuthorizationError when the server refuses the registration.
        """

    def post_mcp(
        self, resource: str, headers: dict[str, str], body: dict
    ) -> tuple[int, dict[str, str], dict]:
        """POST one JSON-RPC request to an MCP endpoint. Returns (status, headers, body)."""
