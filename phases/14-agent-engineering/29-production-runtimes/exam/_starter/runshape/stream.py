"""Stream one agent run to a client as server-sent events, paced by the client."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable


class RunStream:
    """One agent run, streamed as server-sent events (SSE) with backpressure.

    start() runs the agent (an async iterator of step texts) in a task. The run may get
    ahead of the client by at most `ahead` events: once that many events are waiting for
    the client, the agent is not asked for its next step until the client reads one. An
    event counts as read once events() has handed it to the client. Nothing is dropped,
    and a client that disconnects leaves the run paused, not stopped.

    Events are numbered 1, 2, 3, ... and each one is a single SSE message:

        id: 3
        event: step
        data: {"text": "step 3"}

    After the agent's last step comes one final event, data {"status": "done", "steps": n},
    and the stream ends.

    budget_s is the turn budget, in seconds of the agent's own work on clock: the time
    spent inside the agent's __anext__. Time spent paused for the client does not count.
    Once the work reaches budget_s the agent is not asked for another step, and the final
    event is {"status": "budget", "steps": n}.
    """

    def __init__(
        self,
        agent: AsyncIterator[str],
        clock: Callable[[], float],
        ahead: int = 2,
        budget_s: float = 30.0,
    ) -> None:
        if ahead < 1:
            raise ValueError("ahead must be at least 1")
        self._agent = agent
        self._clock = clock
        self.ahead = ahead
        self.budget_s = budget_s

    def start(self) -> None:
        """Start the run in a task of the running event loop."""
        raise NotImplementedError

    async def events(self, last_event_id: str | None = None) -> AsyncIterator[str]:
        """The run's SSE messages, one per string, until the final event.

        A client that reconnects passes the id it saw last (the Last-Event-ID header) and
        gets the events after it, then the live ones. One client reads at a time.
        """
        raise NotImplementedError
