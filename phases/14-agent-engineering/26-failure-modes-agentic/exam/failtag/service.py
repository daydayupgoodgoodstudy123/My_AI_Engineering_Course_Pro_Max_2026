"""Glue used by the trace pipeline: tag, store, gate, watch for drift, tag online."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable

from .cascade import Cascade, cascade_report
from .detectors import tag
from .drift import Alert, DriftMonitor, build_gate
from .online import End, Start, Step, tag_online
from .store import TraceStore
from .trace import Trace


class FailTagService:
    def __init__(self, root: str, clock: Callable[[], float] = time.time, **monitor) -> None:
        self.store = TraceStore(root)
        self.clock = clock
        self.monitor = DriftMonitor(self.store, clock, **monitor)

    def ingest(self, trace: Trace) -> list[str]:
        """Tag a finished trace and store it with its labels."""
        labels = tag(trace)
        self.store.put(trace, labels)
        return labels

    def gate(self, tids: list[str], threshold: float = 0.05) -> list[str]:
        """The modes that fail the build over these stored traces."""
        return build_gate([self.store.get(tid)[1] for tid in tids], threshold)

    def watch(self, tids: list[str]) -> list[Alert]:
        """Drift alerts for a window of stored traces."""
        return self.monitor.check(tids)

    def live(self, events: AsyncIterator[Start | Step | End], host: str = "-") -> AsyncIterator[str]:
        """Tag a live event feed; tag_online defines the wire format."""
        return tag_online(events, self.clock, host)

    def cascades(self, tid: str) -> list[Cascade]:
        """Cascade radius of every root-cause failure in a stored trace."""
        return cascade_report(self.store.get(tid)[0])
