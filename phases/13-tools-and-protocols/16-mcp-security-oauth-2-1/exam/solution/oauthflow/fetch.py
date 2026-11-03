"""Fetch OAuth metadata documents from URLs that someone else chose, under the lesson's SSRF rules.

An authorization server fetches a client's Client ID Metadata Document from the client_id URL;
a client fetches protected-resource and authorization-server metadata. Either way the URL, its
redirects and its DNS answers are controlled by someone else.
"""
from __future__ import annotations

import ipaddress
import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlsplit

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
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


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
        deadline = self.clock() + self.timeout
        visited: set[str] = set()
        redirects = 0
        while True:
            if url in visited:
                raise FetchBlocked(f"a redirect loop back to {url}")
            visited.add(url)
            address = self._checked_address(url)
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise FetchBlocked(f"out of time before {url}")
            try:
                response = self.transport.get(url, connect_to=address, timeout=remaining)
            except TimeoutError as exc:
                raise FetchBlocked(f"no answer from {url} in time") from exc
            if response.status not in REDIRECTS:
                return self._document(url, response)
            if redirects == self.max_redirects:
                raise FetchBlocked(f"more than {self.max_redirects} redirects")
            location = _header(response.headers, "Location")
            if not location:
                raise FetchBlocked(f"a redirect without Location from {url}")
            redirects += 1
            url = urljoin(url, location)

    def _checked_address(self, url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise FetchBlocked(f"not an https URL: {url}")
        host = parts.hostname
        try:
            ipaddress.ip_address(host)
        except ValueError:
            addresses = list(self.resolve(host))
        else:
            addresses = [host]
        if not addresses:
            raise FetchBlocked(f"{host} does not resolve")
        if not all(public_address(address) for address in addresses):
            raise FetchBlocked(f"{host} resolves to an address that may not be fetched")
        return addresses[0]

    def _document(self, url: str, response: Response) -> dict:
        if response.status != 200:
            raise FetchBlocked(f"HTTP {response.status} from {url}")
        media = _header(response.headers, "Content-Type").split(";")[0].strip().lower()
        if media != "application/json":
            raise FetchBlocked(f"{url} is not JSON")
        data = bytearray()
        for chunk in response.body:
            data += chunk
            if len(data) > self.max_bytes:
                raise FetchBlocked(f"{url} is longer than {self.max_bytes} bytes")
        try:
            document = json.loads(bytes(data))
        except ValueError as exc:
            raise FetchBlocked(f"{url} is not valid JSON") from exc
        if not isinstance(document, dict):
            raise FetchBlocked(f"{url} is not a JSON object")
        return document


def resolve_cimd(fetcher: SafeFetcher, client_id: str) -> dict:
    """Fetch and validate the Client ID Metadata Document behind client_id, or raise CimdInvalid.

    client_id must be an https URL with a path ("" and "/" are not paths); otherwise nothing is
    fetched. The document's client_id must equal client_id exactly, with no normalization (a
    trailing slash counts), even when the document was served through a redirect. client_name
    must be a non-empty string and redirect_uris a non-empty list of strings. FetchBlocked from
    the fetch passes through.
    """
    parts = urlsplit(client_id)
    if parts.scheme != "https" or not parts.hostname or parts.path in ("", "/"):
        raise CimdInvalid(f"{client_id!r} is not an https URL with a path")
    document = fetcher.fetch_json(client_id)
    if document.get("client_id") != client_id:
        raise CimdInvalid("the document's client_id is not the URL it was fetched from")
    name = document.get("client_name")
    if not isinstance(name, str) or not name:
        raise CimdInvalid("client_name is required")
    uris = document.get("redirect_uris")
    if not isinstance(uris, list) or not uris or not all(isinstance(u, str) and u for u in uris):
        raise CimdInvalid("redirect_uris must be a non-empty list of strings")
    return document


def _header(headers: Mapping[str, str], name: str) -> str:
    wanted = name.lower()
    return next((value for key, value in headers.items() if key.lower() == wanted), "")
