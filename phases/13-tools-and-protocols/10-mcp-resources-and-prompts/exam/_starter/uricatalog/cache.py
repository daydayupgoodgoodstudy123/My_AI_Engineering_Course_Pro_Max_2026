"""A host's cache of MCP results, in a dbm.dumb file so it survives a restart."""
from __future__ import annotations

import dbm.dumb
from typing import Any, Callable

from .catalog import Caller


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
        raise NotImplementedError

    def get(self, method: str, params: dict[str, Any], caller: Caller, locale: str) -> dict[str, Any] | None:
        """The stored result for this request, exactly as it was put, while it is fresh; else None.

        A result stored at time t with ttlMs n is fresh while the clock reads less than t + n.
        """
        raise NotImplementedError

    def invalidate(self, uri: str) -> int:
        """Forget every stored resources/read result for exactly this URI, for every caller.

        Returns how many entries were removed.
        """
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
