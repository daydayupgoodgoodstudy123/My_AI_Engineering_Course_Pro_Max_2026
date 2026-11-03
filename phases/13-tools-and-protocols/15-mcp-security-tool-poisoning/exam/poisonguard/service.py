"""Glue used by the gateway: approve descriptors, refresh the catalog, stream decisions, audit calls."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from typing import Any

from .audit import redact
from .pins import Pin, PinStore
from .refresh import Refresh, refresh
from .scanner import Catalog, descriptor_digest
from .stream import Page, decision_events


class Gateway:
    def __init__(self, store: PinStore, *, audit_paths: Iterable[str] = (), audit_key: bytes = b"") -> None:
        self.store = store
        self.audit_paths = list(audit_paths)
        self.audit_key = audit_key

    def approve(self, key: str, descriptor: dict[str, Any], publisher: dict[str, str], at: datetime) -> Pin:
        """A reviewer approved this exact descriptor: pin its digest. Approving again lifts a quarantine."""
        return self.store.approve(key, descriptor_digest(descriptor), publisher, at)

    def refresh(self, catalogs: Catalog, at: datetime) -> Refresh:
        """Decide a full refresh against the stored pins (refresh.refresh) and record what it found.

        A pinned tool whose live digest differs from its pin is quarantined in the store as of `at`,
        so it stays out until a reviewer approves it again, even if the server changes it back.
        Nothing else is written: a refresh never pins a tool, however often it has been seen.
        """
        raise NotImplementedError

    def events(self, pages: AsyncIterator[Page]) -> AsyncIterator[str]:
        """NDJSON decision events for a refresh that arrives page by page (stream.decision_events)."""
        return decision_events(pages, self.store.pins())

    def audit_entry(self, record: dict[str, Any]) -> dict[str, Any]:
        """The record as the audit log stores it: the policy's sensitive values become digests."""
        return redact(record, self.audit_paths, self.audit_key)
