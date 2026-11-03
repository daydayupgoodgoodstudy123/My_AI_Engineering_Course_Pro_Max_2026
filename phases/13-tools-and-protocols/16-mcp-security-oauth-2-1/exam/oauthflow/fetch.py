"""Fetch OAuth metadata documents from URLs that someone else chose, under the lesson's SSRF rules.

An authorization server fetches a client's Client ID Metadata Document from the client_id URL;
a client fetches protected-resource and authorization-server metadata. Either way the URL, its
redirects and its DNS answers are controlled by someone else.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .errors import CimdInvalid, FetchBlocked

REDIRECTS = (301, 302, 303, 307, 308)


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: Iterable[bytes]  # read chunk by chunk


class Transport(Protocol):
    def get(self, url: str, *, connect_to: str, timeout: float) -> Response:
        """Open a connection to the IP address connect_to and GET url over it.

        The Host header and the TLS name come from url. Raises TimeoutError when no answer
        arrives within timeout seconds.
        """


def public_address(address: str) -> bool:
    """Whether an IP address (IPv4 or IPv6, as text) may be fetched from.

    Only global unicast addresses may. Loopback, private, link-local, shared (100.64.0.0/10),
    multicast, reserved and unspecified addresses may not.
    """
    raise NotImplementedError


class SafeFetcher:
    """GETs JSON metadata documents, checking every hop of a redirect chain on its own."""

    def __init__(
        self,
        resolve: Callable[[str], list[str]],
        transport: Transport,
        *,
        max_redirects: int = 3,
        max_bytes: int = 64 * 1024,
        timeout: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.resolve = resolve
        self.transport = transport
        self.max_redirects = max_redirects
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.clock = clock

    def fetch_json(self, url: str) -> dict:
        """GET a JSON object from url, following redirects, or raise FetchBlocked.

        Every hop, the first URL and each redirect target alike:
        - must be an https URL with a host;
        - resolves its host once, then and there, even when an earlier hop resolved the same
          host; the answer must hold at least one address and every address in it must pass
          public_address; an IP literal host is checked the same way, without DNS;
        - connects (connect_to) to an address it has just checked, without resolving again.
        A redirect is 301, 302, 303, 307 or 308 with a Location, which may be relative to the URL
        that sent it. At most max_redirects redirects are followed, and a redirect back to a URL
        already visited in this fetch is a loop, refused at once. All hops share one budget of
        timeout seconds: each hop is given what is left of it.

        The final answer must be 200 with the JSON media type (application/json, in any case, with
        or without parameters). Its body is read chunk by chunk and abandoned as soon as it is
        longer than max_bytes, and it must hold a JSON object.
        """
        raise NotImplementedError


def resolve_cimd(fetcher: SafeFetcher, client_id: str) -> dict:
    """Fetch and validate the Client ID Metadata Document behind client_id, or raise CimdInvalid.

    client_id must be an https URL with a path ("" and "/" are not paths); otherwise nothing is
    fetched. The document's client_id must equal client_id exactly, with no normalization (a
    trailing slash counts), even when the document was served through a redirect. client_name
    must be a non-empty string and redirect_uris a non-empty list of strings. FetchBlocked from
    the fetch passes through.
    """
    raise NotImplementedError
