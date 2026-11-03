"""App resources cached as executable content: one blob per HTML body, named by its digest, plus an index."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .wire import RESOURCE_MIME

SCOPES = ("public", "private")


class AppCache:
    """A cache of App resources (resources/read content entries) in one directory.

    The HTML of each entry is stored once, as blobs/<digest>, where the digest is the sha256 hex
    of the HTML's UTF-8 bytes; entries with the same HTML share one blob. An index in the same
    directory keys every entry by its ui:// URI (exactly as the server lists it), the server's
    name and version, and the digest, plus the principal when the entry is private. The rest of
    the content entry (uri, mimeType, _meta) is kept in the index exactly as given.
    A new AppCache on the same directory sees every entry stored before.
    """

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)
        # TODO: lay out the blob directory and the index

    def put(
        self,
        server: dict[str, str],
        content: dict[str, Any],
        *,
        scope: str,
        principal: str | None = None,
    ) -> str:
        """Store one content entry of a resources/read result and return its digest.

        server is the serverInfo ({"name", "version"}) of the server that answered, scope the
        result's cacheScope. A private entry needs the principal it was read for. Only App
        resources are cached: a ui:// URI with mimeType text/html;profile=mcp-app. Anything
        else is a ValueError.
        """
        raise NotImplementedError

    def get(
        self,
        server: dict[str, str],
        uri: str,
        digest: str,
        *,
        principal: str | None = None,
    ) -> dict[str, Any] | None:
        """The content entry stored for this server, URI and digest, exactly as stored; else None.

        A public entry is found for anyone, a private one only for its own principal. The blob
        is checked against the digest on every read: a missing or damaged blob is a miss.
        """
        raise NotImplementedError
