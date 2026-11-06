"""Event-driven agents: subscribers react to events, and what they emit is more events."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Event:
    type: str
    id: str
    payload: str = ""


# A subscriber gets the event and returns the events it emits (or None for none).
Handler = Callable[[Event], Optional[Iterable[Event]]]


@dataclass(frozen=True)
class Delivery:
    depth: int
    event_id: str
    subscriber: str


@dataclass
class Cascade:
    deliveries: list[Delivery] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)
    unhandled: list[str] = field(default_factory=list)


class EventBus:
    """An explicit registry of subscribers per event type, in subscription order.

    A subscriber that raises does not stop delivery to the others: the failure is kept in
    dead_letters as (event id, subscriber name, "ExceptionType: message").
    """

    def __init__(self) -> None:
        self.subscribers: dict[str, list[tuple[str, Handler]]] = {}
        self.dead_letters: list[tuple[str, str, str]] = []
        self._handled: set[tuple[str, str]] = set()

    def subscribe(self, event_type: str, name: str, handler: Handler) -> None:
        self.subscribers.setdefault(event_type, []).append((name, handler))

    def publish(self, event: Event) -> list[Event]:
        """Deliver one event to every subscriber of its type, in subscription order.

        Returns the events the subscribers emitted, in order.
        """
        emitted: list[Event] = []
        for name, handler in self.subscribers.get(event.type, []):
            out = self._deliver(event, name, handler)
            if out is not None:
                emitted.extend(out)
        return emitted

    def cascade(self, event: Event, max_depth: int) -> Cascade:
        """Publish an event, then every event its subscribers emit in turn, breadth first.

        The published event has depth 0; an event emitted while handling a depth-d event
        has depth d + 1. Events are handled depth by depth; within a depth, in the order they
        were emitted; each one by its subscribers in subscription order. An event id reached
        a second time in the same cascade is ignored.

        An event deeper than max_depth is not delivered; its id goes to truncated. An event
        with no subscribers goes to unhandled. Each subscriber handles an event id once over
        the life of the bus: publishing the same event again (a replay) reaches only the
        subscribers that have not handled it yet. A delivery that raised is kept in
        dead_letters, as in publish, and counts as not handled, so a replay tries it again.
        deliveries lists the successful ones.
        """
        if max_depth < 0:
            raise ValueError("max_depth must be at least 0")
        report = Cascade()
        seen: set[str] = set()
        todo: deque[tuple[int, Event]] = deque([(0, event)])
        while todo:
            depth, current = todo.popleft()
            if current.id in seen:
                continue
            seen.add(current.id)
            if depth > max_depth:
                report.truncated.append(current.id)
                continue
            subscribers = self.subscribers.get(current.type, [])
            if not subscribers:
                report.unhandled.append(current.id)
                continue
            for name, handler in subscribers:
                if (current.id, name) in self._handled:
                    continue
                out = self._deliver(current, name, handler)
                if out is None:
                    continue
                self._handled.add((current.id, name))
                report.deliveries.append(Delivery(depth, current.id, name))
                todo.extend((depth + 1, follow_up) for follow_up in out)
        return report

    def _deliver(self, event: Event, name: str, handler: Handler) -> list[Event] | None:
        """Run one subscriber; a failure becomes a dead letter and returns None."""
        try:
            out = handler(event)
        except Exception as exc:
            self.dead_letters.append((event.id, name, f"{type(exc).__name__}: {exc}"))
            return None
        return list(out or ())
