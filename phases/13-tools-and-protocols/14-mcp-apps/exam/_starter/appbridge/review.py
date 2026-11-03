"""How the host reviews a UI resource before a View runs it, and the Views it has mounted."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Any

from .wire import RESOURCE_MIME

CSP_LISTS = ("connectDomains", "resourceDomains", "frameDomains", "baseUriDomains")
# scheme://host[:port], nothing more: no wildcard, no path.
EXACT_ORIGIN = re.compile(r"[a-z][a-z0-9+.-]*://[A-Za-z0-9.-]+(:[0-9]{1,5})?")


class ReviewError(Exception):
    """The host will not let a View run this version of the resource."""


@dataclass(frozen=True)
class Review:
    """The host's verdict on one version of a UI resource."""

    uri: str
    digest: str
    csp: dict[str, tuple[str, ...]]
    permissions: tuple[str, ...]


def content_digest(text: str) -> str:
    """sha256 hex of the HTML's UTF-8 bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def review_resource(content: dict[str, Any], admitted: Collection[str]) -> Review:
    """Review one resources/read content entry.

    The entry must be an MCP App (text/html;profile=mcp-app), its digest must be one the host
    admitted, every CSP list must hold exact origins, and permissions must be an object.
    """
    if content.get("mimeType") != RESOURCE_MIME:
        raise ReviewError(f"{content.get('uri')} is not an MCP App resource")
    digest = content_digest(content["text"])
    if digest not in admitted:
        raise ReviewError(f"{content.get('uri')} digest {digest[:12]} is not admitted")
    ui = (content.get("_meta") or {}).get("ui") or {}
    csp = ui.get("csp") or {}
    lists: dict[str, tuple[str, ...]] = {}
    for key in CSP_LISTS:
        origins = csp.get(key, [])
        if not isinstance(origins, list) or not all(
            isinstance(origin, str) and EXACT_ORIGIN.fullmatch(origin) for origin in origins
        ):
            raise ReviewError(f"csp.{key} must list exact origins")
        lists[key] = tuple(origins)
    permissions = ui.get("permissions", {})
    if not isinstance(permissions, dict):
        raise ReviewError("permissions must be an object")
    return Review(content["uri"], digest, lists, tuple(sorted(permissions)))


class AppMount:
    """One mounted View and the review it runs under.

    The host reviews the resource when it mounts the View, again when a new version of the
    resource replaces it, and again when the host withdraws a digest it had admitted. Between
    those changes, every action the View asks for is checked against the same review.
    replace() and withdraw() only record a change; they never raise.
    """

    def __init__(self, content: dict[str, Any], admitted: Iterable[str]) -> None:
        self._content = content
        self._admitted = set(admitted)

    def replace(self, content: dict[str, Any]) -> None:
        """A new version of the resource was fetched for this View."""
        self._content = content

    def withdraw(self, digest: str) -> None:
        """The host stops admitting a digest, for example because its server was quarantined."""
        self._admitted.discard(digest)

    def review(self) -> Review:
        """The review in force. The host calls this for every action the View asks for.

        Raises ReviewError while the version in force is not admitted. The View never falls
        back to the review of an earlier version.
        """
        return review_resource(self._content, self._admitted)
