"""GenAI spans for one trace, with opt-in content capture by reference."""
from __future__ import annotations

import contextlib
import contextvars
import json
import random
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

REFERENCE_SUFFIX = ".reference_id"


@dataclass
class Span:
    name: str
    kind: str
    trace_id: int
    span_id: int
    parent_span_id: int | None
    start_ns: int
    end_ns: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        """Attribute values are str, bool, int or float. None is not a value: leave the key out."""
        if not isinstance(value, (str, bool, int, float)):
            raise TypeError(
                f"attribute {key!r} must be str, bool, int or float, got {type(value).__name__}"
            )
        self.attributes[key] = value


class ExternalContentStore:
    """In-memory store for captured content (prompts, completions, tool results).

    Content is any JSON value. put() returns a reference id; identical content always
    gets the same id, so a prompt repeated on every turn is stored once.
    """

    def __init__(self) -> None:
        self._by_ref: dict[str, str] = {}
        self._by_text: dict[str, str] = {}

    def __len__(self) -> int:
        return len(self._by_ref)

    def put(self, content: Any) -> str:
        text = json.dumps(content)
        ref = self._by_text.get(text)
        if ref is None:
            ref = f"content_{len(self._by_ref) + 1:03d}"
            self._by_ref[ref] = text
            self._by_text[text] = ref
        return ref

    def get(self, ref: str) -> Any:
        """Return a fresh copy of the stored content. Unknown references raise KeyError."""
        return json.loads(self._by_ref[ref])


class Tracer:
    """Records the GenAI spans of one trace.

    The current span lives in a context variable (contextvars), so every asyncio task sees
    its own current span: concurrent tool calls started from the same agent span are all
    children of that agent span, whatever order they start and end in.

    Timestamps are integer Unix-epoch nanoseconds read from clock (time.time_ns by default),
    so spans recorded by different processes line up on one timeline.

    Content capture is opt-in (capture_content=False records no content at all). With capture
    on, content goes to content_store and the span carries only "<key>.reference_id". Without
    a content_store, the tracer makes its own ExternalContentStore.
    """

    def __init__(
        self,
        *,
        capture_content: bool = False,
        content_store: Any = None,
        clock: Callable[[], int] = time.time_ns,
        rng: random.Random | None = None,
    ) -> None:
        self.capture_content = capture_content
        self.content_store = ExternalContentStore() if content_store is None else content_store
        self.clock = clock
        self._rng = rng or random.Random()
        self.trace_id = self._rng.getrandbits(128)
        self.finished: list[Span] = []
        self.processors: list[Any] = []
        self._current: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
            f"semconv_current_span_{id(self)}", default=None
        )
        self._parents: dict[int, Span | None] = {}

    def current_span(self) -> Span | None:
        return self._current.get()

    def start_span(
        self, name: str, kind: str = "INTERNAL", attributes: dict[str, Any] | None = None
    ) -> Span:
        """Start a child of the current span (a root if there is none) and make it current."""
        parent = self._current.get()
        span = Span(
            name=name,
            kind=kind,
            trace_id=self.trace_id,
            span_id=self._rng.getrandbits(64),
            parent_span_id=parent.span_id if parent else None,
            start_ns=self.clock(),
        )
        for key, value in (attributes or {}).items():
            span.set_attribute(key, value)
        self._parents[span.span_id] = parent
        self._current.set(span)
        return span

    def end_span(self, span: Span, error: BaseException | None = None) -> None:
        """End span, and only span.

        An error sets error.type to the exception's class name. If span is current in this
        context, its parent becomes current again. Every processor's on_end(span) is called.
        """
        span.end_ns = self.clock()
        if error is not None:
            span.set_attribute("error.type", type(error).__name__)
        parent = self._parents.pop(span.span_id, None)
        if self._current.get() is span:
            self._current.set(parent)
        self.finished.append(span)
        for processor in list(self.processors):
            processor.on_end(span)

    @contextlib.contextmanager
    def span(
        self, name: str, kind: str = "INTERNAL", attributes: dict[str, Any] | None = None
    ) -> Iterator[Span]:
        span = self.start_span(name, kind, attributes)
        try:
            yield span
        except BaseException as exc:
            self.end_span(span, exc)
            raise
        self.end_span(span)

    def add_content(self, span: Span, key: str, content: Any) -> None:
        """Capture content for span under key, by reference. Does nothing with capture off."""
        if not self.capture_content:
            return
        span.set_attribute(key + REFERENCE_SUFFIX, self.content_store.put(content))


def captured_content(span: Span, store: Any) -> dict[str, Any]:
    """Resolve every content reference on span: {key: content}."""
    return {
        key[: -len(REFERENCE_SUFFIX)]: store.get(ref)
        for key, ref in span.attributes.items()
        if key.endswith(REFERENCE_SUFFIX)
    }
