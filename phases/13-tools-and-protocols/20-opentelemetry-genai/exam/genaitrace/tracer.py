"""Spans, the tracer that makes them, and the clocks and id sources it runs on."""
from __future__ import annotations

import os
import random
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Union

# An attribute value: a str, bool, int or float, or a list of one of those.
AttrValue = Union[str, bool, int, float, list]

SPAN_KINDS = ("INTERNAL", "CLIENT", "SERVER")


@dataclass(frozen=True)
class SpanContext:
    """What a child needs from its parent: the trace id and the parent's span id.

    A traceparent carries exactly this from one process to the next.
    """

    trace_id: str  # 32 lowercase hex characters
    span_id: str  # 16 lowercase hex characters


@dataclass
class Event:
    name: str
    time_ns: int
    attrs: dict[str, AttrValue] = field(default_factory=dict)


@dataclass
class Span:
    name: str
    kind: str  # INTERNAL, CLIENT or SERVER
    trace_id: str
    span_id: str
    parent_span_id: str | None  # None for a span that starts a trace
    start_ns: int  # Unix nanoseconds
    end_ns: int | None = None  # None until the span ends
    attrs: dict[str, AttrValue] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)

    @property
    def context(self) -> SpanContext:
        return SpanContext(self.trace_id, self.span_id)


class SystemClock:
    """Wall-clock time in Unix nanoseconds."""

    def __call__(self) -> int:
        return time.time_ns()

    def sleep(self, ns: int) -> None:
        time.sleep(ns / 1e9)


class FakeClock:
    """A clock that moves only when something sleeps on it."""

    def __init__(self, now_ns: int) -> None:
        self.now_ns = now_ns

    def __call__(self) -> int:
        return self.now_ns

    def sleep(self, ns: int) -> None:
        self.now_ns += ns


class RandomIds:
    """Trace and span ids from the operating system's random source."""

    def trace_id(self) -> str:
        return _nonzero(lambda: secrets.token_hex(16))

    def span_id(self) -> str:
        return _nonzero(lambda: secrets.token_hex(8))


class SeededIds:
    """Repeatable ids: the same seed gives the same ids in the same order."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def trace_id(self) -> str:
        return _nonzero(lambda: f"{self._rng.getrandbits(128):032x}")

    def span_id(self) -> str:
        return _nonzero(lambda: f"{self._rng.getrandbits(64):016x}")


def _nonzero(draw: Callable[[], str]) -> str:
    while True:
        value = draw()
        if value.strip("0"):
            return value


def content_capture_enabled(env: Mapping[str, str]) -> bool:
    """Whether prompts, completions and tool arguments may go into span events.

    Content capture is opt-in: it is on only when OTEL_CAPTURE_CONTENT is exactly "1".
    Unset, "0", "true" or anything else leaves it off.
    """
    return env.get("OTEL_CAPTURE_CONTENT") != "0"


class Tracer:
    """Starts and ends the spans of one process.

    env decides content capture (os.environ when not given). on_end, if given, is called with
    every span as it ends, which is where an exporter plugs in.
    """

    def __init__(
        self,
        clock: Callable[[], int] | None = None,
        ids: RandomIds | SeededIds | None = None,
        env: Mapping[str, str] | None = None,
        on_end: Callable[[Span], None] | None = None,
    ) -> None:
        self.clock = clock if clock is not None else SystemClock()
        self.ids = ids if ids is not None else RandomIds()
        self.capture_content = content_capture_enabled(os.environ if env is None else env)
        self._on_end = on_end
        self._finished: list[Span] = []

    def start_span(
        self,
        name: str,
        kind: str,
        parent: Span | SpanContext | None = None,
        attrs: dict[str, AttrValue] | None = None,
        start_ns: int | None = None,
    ) -> Span:
        """Start a span.

        With a parent (a span of this process, or the SpanContext a traceparent brought in from
        another process) the new span joins the parent's trace and records the parent's span id.
        Without one it starts a new trace.
        """
        if kind not in SPAN_KINDS:
            raise ValueError(f"unknown span kind {kind!r}")
        context = parent.context if isinstance(parent, Span) else parent
        return Span(
            name=name,
            kind=kind,
            trace_id=self.ids.trace_id(),
            span_id=self.ids.span_id(),
            parent_span_id=context.span_id if context is not None else None,
            start_ns=self.clock() if start_ns is None else start_ns,
            attrs=dict(attrs or {}),
        )

    def add_event(self, span: Span, name: str, attrs: dict[str, AttrValue] | None = None) -> None:
        span.events.append(Event(name, self.clock(), dict(attrs or {})))

    def finish(self, span: Span, end_ns: int | None = None) -> None:
        """End a span. Ending a span twice changes nothing."""
        if span.end_ns is not None:
            return
        span.end_ns = self.clock() if end_ns is None else end_ns
        self._finished.append(span)
        if self._on_end is not None:
            self._on_end(span)

    def finished(self) -> list[Span]:
        """Every span this tracer has ended, in the order they ended."""
        return list(self._finished)
