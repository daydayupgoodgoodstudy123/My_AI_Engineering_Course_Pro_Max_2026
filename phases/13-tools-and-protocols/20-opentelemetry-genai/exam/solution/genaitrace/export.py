"""Ship ended spans to a collector in batches, as OTLP/JSON export requests."""
from __future__ import annotations

import json
from collections.abc import Callable

from .otlp import encode_attributes, to_otlp
from .tracer import Span

SCOPE = {"name": "genaitrace", "version": "0.1.0"}


class BatchExporter:
    """Queues spans as they end and sends them to a collector in batches.

    Attach it with Tracer(on_end=exporter.on_end). Spans wait in the order they ended. A request
    goes out
      - as soon as max_batch spans are waiting, from inside the on_end call that makes it max_batch;
      - on tick(), once the oldest waiting span has waited max_delay_ns or more, by the exporter's
        clock (how long a span has waited counts from the on_end call that queued it);
      - on shutdown(), for whatever is still waiting.
    No request is empty, and none holds more than max_batch spans. Spans that end after shutdown()
    are dropped.

    Each request is one JSON document, handed to send() as UTF-8 bytes:

        {"resourceSpans": [{"resource": {"attributes": <service.name, as OTLP attributes>},
                            "scopeSpans": [{"scope": SCOPE, "spans": [<to_otlp(span)>, ...]}]}]}
    """

    def __init__(
        self,
        send: Callable[[bytes], None],
        *,
        service_name: str,
        clock: Callable[[], int],
        max_batch: int = 512,
        max_delay_ns: int = 5_000_000_000,
    ) -> None:
        if max_batch < 1:
            raise ValueError("max_batch must be at least 1")
        self._send = send
        self.service_name = service_name
        self.clock = clock
        self.max_batch = max_batch
        self.max_delay_ns = max_delay_ns
        self._queue: list[Span] = []
        self._oldest_ns: int | None = None
        self._closed = False

    def on_end(self, span: Span) -> None:
        if self._closed:
            return
        if not self._queue:
            self._oldest_ns = self.clock()
        self._queue.append(span)
        if len(self._queue) >= self.max_batch:
            self._flush()

    def tick(self) -> None:
        if self._queue and self.clock() - self._oldest_ns >= self.max_delay_ns:
            self._flush()

    def shutdown(self) -> None:
        if not self._closed:
            self._flush()
            self._closed = True

    def _flush(self) -> None:
        while self._queue:
            batch, self._queue = self._queue[: self.max_batch], self._queue[self.max_batch :]
            request = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": encode_attributes({"service.name": self.service_name})},
                        "scopeSpans": [{"scope": dict(SCOPE), "spans": [to_otlp(span) for span in batch]}],
                    }
                ]
            }
            self._send(json.dumps(request).encode("utf-8"))
        self._oldest_ns = None
