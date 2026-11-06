"""Trace processors: an NDJSON span log, and a background wrapper for slow trace backends."""
from __future__ import annotations

import json
import queue
import threading
from typing import TextIO

from .tracing import Span, TraceProcessor

_STOP = object()


class NdjsonSpanWriter:
    """Writes every span as one JSON object on its own line, as soon as the span ends:

        {"trace_id": ..., "span_id": ..., "parent_id": ..., "kind": ..., "name": ..., "attributes": {...}}

    Each line is flushed right away, so a reader of the file sees a span once it has ended.
    """

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def on_span_end(self, span: Span) -> None:
        record = {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_id": span.parent_id,
            "kind": span.kind,
            "name": span.name,
            "attributes": span.attributes,
        }
        self.stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.stream.flush()


class BackgroundProcessor:
    """Hands spans to a slow processor on a worker thread, so a run never waits for it.

    on_span_end only queues the span. At most max_queue spans wait for the worker; the span the
    worker is handing over does not count. A span that arrives while max_queue spans are waiting is
    dropped and counted in dropped. The worker hands spans over in the order they ended, and
    shutdown() returns once every queued span has been handed over.
    """

    def __init__(self, processor: TraceProcessor, max_queue: int = 1000) -> None:
        self.processor = processor
        self.dropped = 0
        self._lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue)
        self._worker = threading.Thread(target=self._work, name="span-worker", daemon=True)
        self._worker.start()

    def on_span_end(self, span: Span) -> None:
        try:
            self._queue.put_nowait(span)
        except queue.Full:
            with self._lock:
                self.dropped += 1

    def shutdown(self) -> None:
        self._queue.put(_STOP)
        self._worker.join()

    def _work(self) -> None:
        while True:
            span = self._queue.get()
            if span is _STOP:
                return
            self.processor.on_span_end(span)
