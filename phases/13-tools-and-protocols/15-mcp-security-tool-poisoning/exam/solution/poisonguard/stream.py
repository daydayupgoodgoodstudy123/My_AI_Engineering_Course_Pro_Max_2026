"""A refresh that arrives page by page from many backends, turned into NDJSON decision events."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any

from .pins import Pin
from .refresh import refresh


@dataclass(frozen=True)
class Page:
    """One page of a backend's answer to tools/list."""

    backend: str
    listing: int  # which listing of the backend this page belongs to; newer listings have larger numbers
    tools: list[dict[str, Any]]
    last: bool  # True on the final page of the listing


async def decision_events(pages: AsyncIterator[Page], pins: Mapping[str, Pin]) -> AsyncIterator[str]:
    """Judge each backend's listing once it is complete, and emit the decisions as NDJSON.

    Pages of different backends arrive interleaved. A listing is judged when its last page is in,
    with the refresh rules (refresh.refresh) and only that backend's pins (the keys backend.<tool>),
    and its events go out right then, whatever the other backends are still sending. A listing gives
    one event per tool, and one with decision "removed" for every pin of the backend that the listing
    no longer has, sorted by key. Each event is a JSON object on a line of its own:
    {"backend": ..., "listing": ..., "key": ..., "decision": ...}.

    When a backend starts a newer listing (its tools changed while it was being listed), its older
    listing is dropped if still incomplete, and pages of the older listing that arrive later are
    ignored. A listing still incomplete when the pages run out is never judged.
    """
    newest: dict[str, int] = {}
    open_listings: dict[str, list[dict[str, Any]]] = {}
    async for page in pages:
        seen = newest.get(page.backend)
        if seen is not None and page.listing < seen:
            continue
        if seen is None or page.listing > seen:
            newest[page.backend] = page.listing
            open_listings[page.backend] = []
        tools = open_listings.get(page.backend)
        if tools is None:  # this listing has been judged already
            continue
        tools.extend(page.tools)
        if not page.last:
            continue
        del open_listings[page.backend]
        own = {key: pin for key, pin in pins.items() if key.partition(".")[0] == page.backend}
        result = refresh(own, {page.backend: tools})
        events = [(d.key, d.status) for d in result.decisions] + [(key, "removed") for key in result.removed]
        for key, decision in sorted(events):
            event = {"backend": page.backend, "listing": page.listing, "key": key, "decision": decision}
            yield json.dumps(event) + "\n"
