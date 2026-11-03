"""A native app's authorization flows on the wire: the browser URL, the loopback redirect, the token POST."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .client import McpClient
from .model import PendingAuth

FORM = "application/x-www-form-urlencoded"

# post(url, headers, body) sends one HTTP POST and returns (status, parsed JSON body)
TokenPost = Callable[[str, dict[str, str], bytes], Awaitable[tuple[int, dict[str, Any]]]]


@dataclass(frozen=True)
class Outcome:
    """What became of one redirect that reached the loopback listener.

    kind is "token", "denied" or "rejected". resource is the flow's resource, or None when the
    redirect matched no flow. A rejection's reason is unknown_state, expired, issuer_mismatch or
    no_code. A denial carries the server's error as reason and its error_description.
    """

    kind: str
    resource: str | None
    reason: str = ""
    description: str = ""


class LoopbackDesk:
    """The authorization flows a native client has open, and the listener that finishes them."""

    def __init__(
        self,
        client: McpClient,
        post: TokenPost,
        *,
        clock: Callable[[], float] = time.monotonic,
        ttl: float = 600.0,
    ) -> None:
        self.client = client
        self.post = post
        self.clock = clock
        self.ttl = ttl
        self._flows: dict[str, tuple[PendingAuth, float]] = {}

    def begin(self, resource: str, scope: str) -> str:
        """Open a flow for resource and scope (client.start) and return the URL for the browser.

        The URL is the authorization endpoint with the request parameters added as an
        application/x-www-form-urlencoded query, after any query the endpoint already has.
        """
        raise NotImplementedError

    async def serve(self, redirects: AsyncIterator[str]) -> AsyncIterator[Outcome]:
        """Finish flows as their redirects arrive, yielding one Outcome per redirect.

        Redirects come in any order, from any number of flows, and each is handled like this:
        1. Its state finds the flow. A flow takes exactly one redirect and is closed as soon as one
           matches it, before anything else is checked; a state that matches no open flow is
           rejected as unknown_state.
        2. A flow opened more than ttl seconds ago is rejected as expired.
        3. A present iss must equal the flow's issuer exactly. Otherwise the redirect is rejected as
           issuer_mismatch, and nothing else in it is used or shown, error_description included.
        4. An error redirect is denied with the server's error and error_description.
        5. Otherwise the code goes to the token endpoint in an application/x-www-form-urlencoded
           POST of client.token_form(): grant_type, code, redirect_uri, client_id, code_verifier
           and resource. An error answer is denied the same way; a token is kept with client.store.

        Token requests of different flows run concurrently: a slow token endpoint never holds up
        other redirects, and each Outcome is yielded as soon as it is known. serve ends when the
        redirects end and every token request has finished.
        """
        raise NotImplementedError
