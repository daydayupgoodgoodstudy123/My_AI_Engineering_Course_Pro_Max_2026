"""App resources cached as executable content: one blob per HTML body, named by its digest, plus an index."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .blob_io import load_html, store_html
from .wire import RESOURCE_MIME

SCOPES = ("public", "private")


class AppCache:
    """A cache of App resources (resources/read content entries) in one directory.

    The HTML of each entry is stored once, as blobs/<digest>, where the digest is the sha256 hex
    of the HTML's UTF-8 bytes; entries with the same HTML share one blob. An index in the same
    directory keys every entry by its ui:// URI (exactly as the server lists it), the server's
    name and version, and the digest, plus the principal when the entry is private. The rest of
    the content entry (uri, mimeType, _meta) is kept in the index exactly as given.
    A new AppCache on the same directory sees every entry stored before. Public put/get use the
    given blob_io helpers for raw HTML; implement _put_entry, _get_entry and _key for the index.
    Sharing HTML never merges entries or their security metadata.
    """

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)
        self.blobs = self.root / "blobs"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

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
        uri = content.get("uri")
        if not isinstance(uri, str) or not uri.startswith("ui://"):
            raise ValueError(f"only ui:// resources are cached, got {uri!r}")
        if content.get("mimeType") != RESOURCE_MIME:
            raise ValueError(f"{uri} is not an MCP App: mimeType {content.get('mimeType')!r}")
        if scope not in SCOPES:
            raise ValueError(f"cacheScope must be public or private, got {scope!r}")
        if scope == "private" and not principal:
            raise ValueError("a private entry needs the principal it was read for")
        digest = store_html(self.blobs, content["text"])
        self._put_entry(server, content, digest, scope=scope, principal=principal)
        return digest

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
        record = self._get_entry(server, uri, digest, principal=principal)
        if record is None:
            return None
        text = load_html(self.blobs, digest)
        if text is None:
            return None
        return {**record, "text": text}

    def _put_entry(
        self, server: dict[str, str], content: dict[str, Any], digest: str, *,
        scope: str, principal: str | None,
    ) -> None:
        """Persist this entry's complete non-text fields under its identity key.

        HTML sharing never shares CSP, permissions or other _meta. Storing the same identity
        again replaces its whole record, including removed metadata. Other entries stay as they
        were, and every record survives a new AppCache on the same folder.
        """
        raise NotImplementedError

    def _get_entry(
        self, server: dict[str, str], uri: str, digest: str, *, principal: str | None,
    ) -> dict[str, Any] | None:
        """Find this identity's non-text record, checking public before this principal's private key.

        Metadata is never borrowed from another record that happens to reference the same blob.
        """
        raise NotImplementedError

    def _load(self) -> dict[str, Any]:
        try:
            return json.loads(self.index_path.read_bytes())
        except FileNotFoundError:
            return {}


def _key(server: dict[str, str], uri: str, digest: str, principal: str | None) -> str:
    """An index key that distinguishes URI, server name, server version, HTML digest and principal.

    principal is None for a public record and the authenticated principal for a private record.
    """
    raise NotImplementedError


def _write(path: Path, data: bytes) -> None:
    """Replace a file in one step: write a temporary file next to it, then rename it."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
