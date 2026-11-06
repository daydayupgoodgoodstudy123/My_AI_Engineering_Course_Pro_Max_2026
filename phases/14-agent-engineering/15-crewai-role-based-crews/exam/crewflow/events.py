"""An async Flow whose steps are logged in logfmt the moment they complete."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable
from typing import Any, Callable

AsyncStep = Callable[[Any], Awaitable["tuple[str, Any] | None"]]


def logfmt(pairs: list[tuple[str, str]]) -> str:
    r"""One logfmt line, without its newline: key=value pairs separated by single spaces.

    A value is written bare unless it is empty or holds a space, a double quote, an equals sign,
    a backslash, a newline, a carriage return or a tab. Then it is written in double quotes, with
    the backslash escapes \\, \", \n, \r and \t.
    """
    raise NotImplementedError


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
        raise NotImplementedError
