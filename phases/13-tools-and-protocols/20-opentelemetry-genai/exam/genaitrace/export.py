"""Ship ended spans to a collector in batches, as OTLP/JSON export requests."""
from __future__ import annotations

from collections.abc import Callable

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
        # TODO: the queue

    def on_end(self, span: Span) -> None:
        raise NotImplementedError

    def tick(self) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError
