"""The MCP client side of the authorization code flow, in process.

Discovery, PKCE, the authorization response check, tokens bound to (issuer, resource), and tool
calls. loopback.py runs the same flow over a real loopback redirect.
"""
from __future__ import annotations

import secrets
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from .discovery import discover
from .errors import AuthorizationError, IssuerMismatch, McpError, StateMismatch, TokenError
from .model import Discovery, PendingAuth, TokenRecord
from .net import Network
from .pkce import pkce_pair
from .stepup import parse_bearer_challenge, step_up_scope

PROTOCOL_VERSION = "2026-07-28"


class Enroller(Protocol):
    def client_id_for(self, issuer: str, metadata: Mapping[str, Any]) -> str:
        """The client id to present to issuer, given that issuer's metadata."""


def check_response(pending: PendingAuth, response: Mapping[str, str]) -> str:
    """Validate an authorization response and return its code.

    The state must be this flow's own. When iss is present it must equal the recorded issuer
    exactly (RFC 9207): no case folding, no trailing-slash change, no default-port removal, no
    percent-decoding. A present iss is checked even when the server's metadata does not advertise
    authorization_response_iss_parameter_supported. Nothing else in the response is used before
    these checks pass.
    """
    if response.get("state") != pending.state:
        raise StateMismatch("the authorization response belongs to another flow")
    iss = response.get("iss")
    if iss is not None and iss.rstrip("/").lower() != pending.issuer.rstrip("/").lower():
        raise IssuerMismatch("the authorization response names another issuer")
    code = response.get("code")
    if not code:
        raise AuthorizationError("invalid_request", "the authorization response carries no code")
    return code


class McpClient:
    """Calls tools on MCP resources. Tokens are kept per (issuer, resource)."""

    def __init__(
        self,
        net: Network,
        enrollment: Enroller,
        *,
        redirect_uri: str,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.net = net
        self.enrollment = enrollment
        self.redirect_uri = redirect_uri
        self.clock = clock
        self.tokens: dict[tuple[str, str], TokenRecord] = {}
        self._next_id = 1

    def discovery(self, resource: str) -> Discovery:
        """What discovery found for resource.

        Each resource is discovered once and the result is reused by every later login and call.
        Two resources on one origin are still two resources, each with its own metadata and issuer.
        """
        return discover(self.net, resource)

    def start(self, resource: str, scope: str) -> tuple[PendingAuth, dict[str, str]]:
        """Begin a flow: a fresh PKCE pair and state, and the authorization request parameters."""
        found = self.discovery(resource)
        metadata = found.server_metadata
        client_id = self.enrollment.client_id_for(found.issuer, metadata)
        verifier, challenge = pkce_pair()
        pending = PendingAuth(
            issuer=found.issuer,
            resource=resource,
            client_id=client_id,
            redirect_uri=self.redirect_uri,
            scope=scope,
            state=secrets.token_urlsafe(16),
            verifier=verifier,
            authorization_endpoint=metadata["authorization_endpoint"],
            token_endpoint=metadata["token_endpoint"],
        )
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "state": pending.state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
        }
        return pending, params

    def token_form(self, pending: PendingAuth, code: str) -> dict[str, str]:
        """The token request fields: the code, the verifier, and the same redirect URI and resource."""
        return {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": pending.redirect_uri,
            "client_id": pending.client_id,
            "code_verifier": pending.verifier,
            "resource": pending.resource,
        }

    def store(self, pending: PendingAuth, answer: Mapping[str, Any]) -> TokenRecord:
        """Keep a token endpoint answer under (issuer, resource). An error answer raises TokenError."""
        if "error" in answer or "access_token" not in answer:
            raise TokenError(
                str(answer.get("error", "invalid_response")), str(answer.get("error_description", ""))
            )
        record = TokenRecord(
            issuer=pending.issuer,
            resource=pending.resource,
            access_token=answer["access_token"],
            scope=answer.get("scope", pending.scope),
            expires_at=int(self.clock()) + int(answer.get("expires_in", 3600)),
            refresh_token=answer.get("refresh_token"),
        )
        self.tokens[(pending.issuer, pending.resource)] = record
        return record

    def login(self, resource: str, scope: str) -> TokenRecord:
        """Run the whole flow for resource and scope, and keep the token."""
        pending, params = self.start(resource, scope)
        response = self.net.authorize(pending.authorization_endpoint, params)
        code = check_response(pending, response)
        answer = self.net.token(pending.token_endpoint, self.token_form(pending, code))
        return self.store(pending, answer)

    def call(self, resource: str, tool: str, arguments: dict | None = None) -> dict:
        """Call one tool with the token kept for (issuer, resource) and return its result.

        Needs a token from login(); without one it raises LookupError. Any HTTP status other than
        200 raises McpError.
        """
        found = self.discovery(resource)
        token = self.tokens.get((found.issuer, resource))
        if token is None:
            raise LookupError(f"no token for {resource}; log in first")
        request_id = self._next_id
        self._next_id += 1
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": dict(arguments or {}),
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                    "io.modelcontextprotocol/clientCapabilities": {},
                    "io.modelcontextprotocol/clientInfo": {"name": "oauthflow", "version": "1.0.0"},
                },
            },
        }
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": tool,
        }
        status, answer_headers, answer = self.net.post_mcp(resource, headers, body)
        if status != 200:
            raise McpError(status, answer_headers, answer)
        return answer["result"]

    def call_with_step_up(self, resource: str, tool: str, arguments: dict | None = None) -> dict:
        """Call a tool, and recover once when the server refuses the token.

        - 403 with a Bearer insufficient_scope challenge: run a new flow for the scope granted so
          far plus the challenged scope (step_up_scope), then retry. The challenge is
          authoritative, so its scope is asked for even when scopes_supported does not list it.
          If that flow fails (the user declines), the error propagates and the current token is
          kept: it still works for what it was granted.
        - 401: the token is no longer accepted. Drop it first, then run a new flow for the scope
          it had, and retry.
        - Anything else, or a failure of the retry, raises McpError: one recovery per call.
        """
        raise NotImplementedError


def _header(headers: Mapping[str, str], name: str) -> str:
    wanted = name.lower()
    return next((value for key, value in headers.items() if key.lower() == wanted), "")
