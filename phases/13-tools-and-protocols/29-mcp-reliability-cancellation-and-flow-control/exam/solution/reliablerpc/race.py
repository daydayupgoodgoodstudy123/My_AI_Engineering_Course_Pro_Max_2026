"""Every interleaving of the cancellation race, checked: the client, the server and the wire."""
from __future__ import annotations

import copy
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .buffer import BoundedSseBuffer
from .coordinator import RequestCoordinator
from .wire import CANCELLED, COMPLETED, STDIO, is_progress, notification

EVENTS = ("start", "progress", "cancel", "timeout", "complete", "server_hears", "client_hears")
RESULT = {"content": [{"type": "text", "text": "report ready"}]}


class Client:
    """The caller's side of the request: waiting, then done or abandoned."""

    def __init__(self) -> None:
        self.status = "waiting"

    def abandon(self) -> None:
        if self.status == "waiting":
            self.status = "abandoned"

    def receive(self, kind: str) -> bool:
        """Take a "progress" or "response" for the request. True when the client used it."""
        if self.status != "waiting":
            return False
        if kind == "response":
            self.status = "done"
        return True


@dataclass(frozen=True)
class World:
    """One state of the race. Worlds that compare equal are the same state.

    problem is set when the step that produced this world broke an invariant.
    """

    server: str = "absent"  # the request's state at the server; "absent" until it starts
    worker_done: bool = False
    progress_reports: int = 0
    to_server: tuple[str, ...] = ()  # cancellations on their way to the server
    to_client: tuple[str, ...] = ()  # "progress" and "response" on their way to the client
    client: str = "waiting"
    first_terminal: str | None = None
    problem: str | None = None
    coordinator: Any = field(default=None, compare=False, repr=False)
    caller: Any = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class Counterexample:
    trace: tuple[str, ...]
    problem: str


class RaceModel:
    """One stdio tools/call (id 1, progress token "p-1") between a Client and a RequestCoordinator.

    Events, any of which may happen whenever it is possible:
    - start: the server starts the request;
    - progress: the worker reports progress (at most max_progress times, until it completes);
    - complete: the worker finishes, and the server completes the request;
    - cancel, timeout: the client gives up (the user cancelled, or its deadline passed) and
      sends notifications/cancelled;
    - server_hears: the oldest cancellation in flight reaches the server;
    - client_hears: the oldest message in flight reaches the client.

    Invariants: the server sends nothing for a request it has cancelled; a request never leaves
    its first terminal state; the client uses nothing for a request it has abandoned.
    """

    def __init__(
        self,
        coordinator_class: type = RequestCoordinator,
        client_class: type = Client,
        *,
        max_progress: int = 3,
    ) -> None:
        self.coordinator_class = coordinator_class
        self.client_class = client_class
        self.max_progress = max_progress

    def initial(self) -> World:
        return World(coordinator=self.coordinator_class(BoundedSseBuffer(64)), caller=self.client_class())

    def step(self, world: World, event: str) -> World | None:
        """The world after event, or None when event cannot happen in world."""
        if event not in EVENTS:
            raise ValueError(f"unknown event {event!r}")
        if not self._possible(world, event):
            return None
        coordinator = copy.deepcopy(world.coordinator)
        client = copy.deepcopy(world.caller)
        to_server, to_client = world.to_server, world.to_client
        worker_done, reports, used = world.worker_done, world.progress_reports, None
        if event == "start":
            coordinator.start(1, "tools/call", transport=STDIO, progress_token="p-1")
        elif event == "progress":
            reports += 1
            coordinator.progress(1, reports)
        elif event == "complete":
            worker_done = True
            coordinator.complete(1, RESULT)
        elif event in ("cancel", "timeout"):
            client.abandon()
            to_server += ("user cancelled" if event == "cancel" else "deadline passed",)
        elif event == "server_hears":
            reason, to_server = to_server[0], to_server[1:]
            coordinator.receive_stdio_cancellation(
                notification("notifications/cancelled", {"requestId": 1, "reason": reason})
            )
        else:
            kind, to_client = to_client[0], to_client[1:]
            used = kind if client.receive(kind) else None
        sent = tuple("progress" if is_progress(m) else "response" for m in coordinator.channel.drain())
        request = coordinator.requests.get(1)
        server = request.state if request is not None else "absent"
        problem = None
        if world.server == CANCELLED and sent:
            problem = f"the server sent a {sent[0]} after cancelling the request"
        elif world.first_terminal is not None and server != world.first_terminal:
            problem = f"the request went from {world.first_terminal} to {server}"
        elif used is not None and world.client == "abandoned":
            problem = f"the client used a {used} after abandoning the request"
        terminal = world.first_terminal or (server if server in (COMPLETED, CANCELLED) else None)
        return World(
            server, worker_done, reports, to_server, to_client + sent, client.status, terminal, problem,
            coordinator, client,
        )

    def _possible(self, world: World, event: str) -> bool:
        if event == "start":
            return world.server == "absent"
        if event == "progress":
            return world.server != "absent" and not world.worker_done and world.progress_reports < self.max_progress
        if event == "complete":
            return world.server != "absent" and not world.worker_done
        if event in ("cancel", "timeout"):
            return world.client == "waiting"
        if event == "server_hears":
            return bool(world.to_server)
        return bool(world.to_client)


def explore(model: RaceModel, events: Iterable[str], *, max_depth: int) -> Counterexample | None:
    """Search every sequence of at most max_depth events, breadth first, for a broken invariant.

    Only the given events are tried, in the given order. Each distinct world is explored once.
    Returns Counterexample(trace, problem) for the shortest sequence that breaks an invariant
    (among sequences of that length, the first in the order of events), trace being the tuple of
    its events; None when no sequence does.
    """
    events = tuple(events)
    start = model.initial()
    if start.problem is not None:
        return Counterexample((), start.problem)
    seen = {start}
    frontier = deque([(start, ())])
    while frontier:
        world, trace = frontier.popleft()
        if len(trace) >= max_depth:
            continue
        for event in events:
            after = model.step(world, event)
            if after is None or after in seen:
                continue
            path = trace + (event,)
            if after.problem is not None:
                return Counterexample(path, after.problem)
            seen.add(after)
            frontier.append((after, path))
    return None
