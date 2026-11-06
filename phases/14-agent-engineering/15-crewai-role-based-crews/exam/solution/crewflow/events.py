"""An async Flow whose steps are logged in logfmt the moment they complete."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable
from typing import Any, Callable

AsyncStep = Callable[[Any], Awaitable["tuple[str, Any] | None"]]

_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def logfmt(pairs: list[tuple[str, str]]) -> str:
    r"""One logfmt line, without its newline: key=value pairs separated by single spaces.

    A value is written bare unless it is empty or holds a space, a double quote, an equals sign,
    a backslash, a newline, a carriage return or a tab. Then it is written in double quotes, with
    the backslash escapes \\, \", \n, \r and \t.
    """
    return " ".join(f"{key}={_value(value)}" for key, value in pairs)


def _value(text: str) -> str:
    if text and not any(c in ' "=' or c in _ESCAPES for c in text):
        return text
    return '"' + "".join(_ESCAPES.get(c, c) for c in text) + '"'


class AsyncFlow:
    """A Flow whose steps are coroutines. @flow.start and @flow.listen(topic) register steps,
    as in Flow; a step returns (topic, output) to emit topic, or None to end its branch."""

    def __init__(self) -> None:
        self._start: AsyncStep | None = None
        self._listeners: dict[str, list[AsyncStep]] = {}

    def start(self, fn: AsyncStep) -> AsyncStep:
        self._start = fn
        return fn

    def listen(self, topic: str) -> Callable[[AsyncStep], AsyncStep]:
        def register(fn: AsyncStep) -> AsyncStep:
            self._listeners.setdefault(topic, []).append(fn)
            return fn

        return register

    async def run(self, payload: Any) -> AsyncIterator[str]:
        r"""Run the flow on payload and yield one logfmt line, ending in "\n", per completed step.

        The start step runs on payload. When a step emits a topic, every listener of that topic
        starts at once on the output, so the listeners of one topic run concurrently. A step that
        returns None ends its branch, and so does a topic nobody listens to. The run is over when
        no step is running.

        A step is logged the moment it completes, while other steps may still be running:
            step=<name> topic=<topic> duration_ms=<ms> out=<output>
        A step that returned None logs only step and duration_ms. duration_ms is the step's own
        run time, in whole milliseconds. A step that raises logs
            step=<name> duration_ms=<ms> error=<ExceptionType>: <message>
        and then the steps still running are cancelled and the exception propagates.
        """
        if self._start is None:
            raise ValueError("the flow has no start step")
        finished: asyncio.Queue = asyncio.Queue()
        running: set[asyncio.Task] = set()

        def launch(step: AsyncStep, value: Any) -> None:
            task = asyncio.create_task(_timed(step, value, finished))
            running.add(task)
            task.add_done_callback(running.discard)

        launch(self._start, payload)
        pending = 1
        try:
            while pending:
                step, result, error, ms = await finished.get()
                pending -= 1
                name = step.__name__
                if error is not None:
                    yield logfmt(
                        [("step", name), ("duration_ms", str(ms)), ("error", f"{type(error).__name__}: {error}")]
                    ) + "\n"
                    raise error
                if result is None:
                    yield logfmt([("step", name), ("duration_ms", str(ms))]) + "\n"
                    continue
                topic, out = result
                for listener in self._listeners.get(topic, []):
                    launch(listener, out)
                    pending += 1
                yield logfmt([("step", name), ("topic", topic), ("duration_ms", str(ms)), ("out", str(out))]) + "\n"
        finally:
            leftovers = list(running)
            for task in leftovers:
                task.cancel()
            if leftovers:
                await asyncio.gather(*leftovers, return_exceptions=True)


async def _timed(step: AsyncStep, value: Any, finished: asyncio.Queue) -> None:
    began = time.perf_counter()
    try:
        result = await step(value)
    except Exception as exc:
        finished.put_nowait((step, None, exc, _elapsed_ms(began)))
    else:
        finished.put_nowait((step, result, None, _elapsed_ms(began)))


def _elapsed_ms(began: float) -> int:
    return round((time.perf_counter() - began) * 1000)
