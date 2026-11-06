"""Stream one agent run to a client as server-sent events, paced by the client."""
from __future__ import annotations

import asyncio
import json
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
        self._log: list[str] = []  # every event so far, as SSE text; event n is _log[n - 1]
        self._read = 0  # id of the last event the client has received
        self._final_id: int | None = None
        self._changed = asyncio.Condition()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start the run in a task of the running event loop."""
        self._task = asyncio.get_running_loop().create_task(self._produce())

    async def events(self, last_event_id: str | None = None) -> AsyncIterator[str]:
        """The run's SSE messages, one per string, until the final event.

        A client that reconnects passes the id it saw last (the Last-Event-ID header) and
        gets the events after it, then the live ones. One client reads at a time.
        """
        index = 0 if last_event_id is None else int(last_event_id)
        if not 0 <= index <= len(self._log):
            raise ValueError(f"this run has no event {last_event_id!r}")
        async with self._changed:
            self._read = index
            self._changed.notify_all()
        while index != self._final_id:
            async with self._changed:
                await self._changed.wait_for(lambda: index < len(self._log))
                chunk = self._log[index]
                index += 1
                self._read = index
                self._changed.notify_all()
            yield chunk

    async def _produce(self) -> None:
        worked = 0.0
        steps = 0
        status = "done"
        while True:
            async with self._changed:
                await self._changed.wait_for(lambda: len(self._log) - self._read < self.ahead)
            if worked >= self.budget_s:
                status = "budget"
                break
            started = self._clock()
            try:
                text = await self._agent.__anext__()
            except StopAsyncIteration:
                break
            worked += self._clock() - started
            steps += 1
            await self._emit("step", {"text": text})
        if status == "budget":
            aclose = getattr(self._agent, "aclose", None)
            if aclose is not None:
                await aclose()
        await self._emit("final", {"status": status, "steps": steps})

    async def _emit(self, kind: str, data: dict) -> None:
        async with self._changed:
            event_id = len(self._log) + 1
            self._log.append(f"id: {event_id}\nevent: {kind}\ndata: {json.dumps(data)}\n\n")
            if kind == "final":
                self._final_id = event_id
            self._changed.notify_all()
