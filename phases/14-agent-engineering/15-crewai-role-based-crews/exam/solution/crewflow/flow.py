"""Flow: an event-driven graph that code owns, the shape the lesson recommends for production."""
from __future__ import annotations

from collections import deque
from typing import Any, Callable

Step = Callable[[Any], "tuple[str, Any] | None"]


class Flow:
    """A deterministic, event-driven workflow.

    @flow.start marks the entry step and @flow.listen(topic) a step that runs when another step
    emits topic. A step returns (topic, output) to emit topic with that output, or None to end
    its branch. A topic may have several listeners: every one of them runs on the emitted
    output, in registration order. Emitted events are handled first in, first out.
    """

    def __init__(self) -> None:
        self._start: Step | None = None
        self._listeners: dict[str, list[Step]] = {}

    def start(self, fn: Step) -> Step:
        self._start = fn
        return fn

    def listen(self, topic: str) -> Callable[[Step], Step]:
        def register(fn: Step) -> Step:
            self._listeners.setdefault(topic, []).append(fn)
            return fn

        return register

    def kickoff(self, payload: Any) -> list[tuple[str, str | None, Any]]:
        """Run the flow on payload and return its trace, one (step name, topic, output) per step
        that ran, in the order the steps ran. A step that ended its branch has topic and output None.
        """
        if self._start is None:
            raise ValueError("the flow has no start step")
        trace: list[tuple[str, str | None, Any]] = []
        pending: deque[tuple[Step, Any]] = deque([(self._start, payload)])
        while pending:
            step, value = pending.popleft()
            result = step(value)
            if result is None:
                trace.append((step.__name__, None, None))
                continue
            topic, out = result
            trace.append((step.__name__, topic, out))
            for listener in self._listeners.get(topic, []):
                pending.append((listener, out))
        return trace
