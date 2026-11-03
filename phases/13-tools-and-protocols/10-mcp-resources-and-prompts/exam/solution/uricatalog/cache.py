"""A host's cache of MCP results, in a dbm.dumb file so it survives a restart."""
from __future__ import annotations

import dbm.dumb
import json
from typing import Any, Callable

from .catalog import Caller

SCOPES = ("public", "private")


class ResponseCache:
    """Results the host may reuse, stored under their own cache hints.

    ttlMs says how long a result stays fresh, in integer milliseconds on the injected clock; a
    result with ttlMs 0, or without cache hints, is never stored. cacheScope "public" may be
    reused for any caller and "private" only for the tenant and user it was fetched for. MCP
    defines no other scope, so anything else is not stored either.

    The key holds every request dimension that changes a result: the method, the resource URI,
    the pagination cursor and the host's locale, plus the tenant and user for a private result.
    Two different requests never share a key, whatever their tenant, user, URI or cursor contain.
    """

    def __init__(self, path: str, clock: Callable[[], int]) -> None:
        self._db = dbm.dumb.open(path, "c")
        self._clock = clock

    def put(self, method: str, params: dict[str, Any], caller: Caller, locale: str, result: dict[str, Any]) -> bool:
        """Store result for this request if its cache hints allow it; return whether it was stored."""
        ttl = result.get("ttlMs")
        scope = result.get("cacheScope")
        if type(ttl) is not int or ttl <= 0 or scope not in SCOPES:
            return False
        entry = {"expiresAt": self._clock() + ttl, "result": result}
        # ensure_ascii keeps a lone surrogate (text cut mid-emoji) as an escape, so it round-trips
        self._db[_key(scope, method, params, caller, locale)] = json.dumps(entry).encode("ascii")
        return True

    def get(self, method: str, params: dict[str, Any], caller: Caller, locale: str) -> dict[str, Any] | None:
        """The stored result for this request, exactly as it was put, while it is fresh; else None.

        A result stored at time t with ttlMs n is fresh while the clock reads less than t + n.
        """
        now = self._clock()
        for scope in ("private", "public"):
            raw = self._db.get(_key(scope, method, params, caller, locale))
            if raw is not None:
                entry = json.loads(raw)
                if now < entry["expiresAt"]:
                    return entry["result"]
        return None

    def invalidate(self, uri: str) -> int:
        """Forget every stored resources/read result for exactly this URI, for every caller.

        Returns how many entries were removed.
        """
        removed = 0
        for key in list(self._db.keys()):  # dbm keys come back as bytes
            scope, method, key_uri, *_ = json.loads(key)
            if method == "resources/read" and key_uri == uri:
                del self._db[key]
                removed += 1
        return removed

    def close(self) -> None:
        self._db.close()


def _key(scope: str, method: str, params: dict[str, Any], caller: Caller, locale: str) -> bytes:
    """A JSON array of the request's dimensions: unlike joining with a separator, it is injective."""
    fields = [scope, method, params.get("uri"), params.get("cursor"), locale]
    if scope == "private":
        fields += [caller.tenant, caller.user]
    return json.dumps(fields).encode("ascii")
