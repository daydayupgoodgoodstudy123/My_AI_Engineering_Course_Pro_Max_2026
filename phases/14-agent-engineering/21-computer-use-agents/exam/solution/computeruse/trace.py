"""Per-step traces of long unattended runs, one logfmt line per step."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

from .capture import CaptureStore
from .safety import Action, SafetyClassifier
from .screen import Screen

_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


class AsyncDesktop(Protocol):
    async def capture(self) -> tuple[Screen, bytes]: ...
    async def click(self, x: int, y: int) -> Any: ...
    async def type(self, text: str) -> Any: ...


def logfmt(pairs: list[tuple[str, object]]) -> str:
    """key=value pairs joined by single spaces, without a trailing newline.

    A value is written bare when it is non-empty and has no space, '=', '"', backslash or
    control character. Otherwise it is wrapped in double quotes, with backslash, double
    quote, newline, carriage return and tab written as \\\\, \\", \\n, \\r and \\t.
    """
    out = []
    for key, value in pairs:
        text = str(value)
        if text and not any(c in ' ="\\' or c < " " or c == "\x7f" for c in text):
            out.append(f"{key}={text}")
        else:
            out.append(f'{key}="' + "".join(_ESCAPES.get(c, c) for c in text) + '"')
    return " ".join(out)


async def trace_run(
    actions: AsyncIterator[Action],
    desktop: AsyncDesktop,
    classifier: SafetyClassifier,
    store: CaptureStore,
    clock: Callable[[], int] = time.monotonic_ns,
) -> AsyncIterator[str]:
    """Run an unattended session and yield one logfmt line per step, as each step finishes.

    For every action taken from actions: capture the screen, store the screenshot in
    store, assess the action against that screen, then run it if it is allowed. Nobody is
    there to confirm, so an action that needs confirmation is held and not run.

    Each step's line is yielded before the next action is taken from actions:
      step kind [x y | text | url] element verdict [reason] shot ms
    - x and y for a click, text for type, url for navigate, as the action gives them
    - element: label of the element the action lands on, empty when there is none
    - verdict: ok, blocked, held, or error when running the action raised
    - reason: the classifier's reason for blocked and held, the exception text for error
    - shot: the first 12 hex digits of the screenshot's SHA-256 digest
    - ms: whole milliseconds by clock (nanoseconds) from the capture to the end of the step;
      the time spent waiting for the next action is not part of any step
    After the last step comes "run=ok steps=<n>". A step that errors ends the run: its
    line is followed by "run=failed failed_step=<n>" and no further action is taken.
    Every line ends with a newline.
    """
    n = 0
    async for action in actions:
        n += 1
        start = clock()
        screen, frame = await desktop.capture()
        digest = store.put(frame)
        verdict = classifier.assess(action, screen)
        pairs: list[tuple[str, object]] = [("step", n), ("kind", action.kind)]
        if action.kind == "click":
            pairs += [("x", action.args["x"]), ("y", action.args["y"])]
        elif action.kind == "type":
            pairs.append(("text", action.args["text"]))
        elif action.kind == "navigate":
            pairs.append(("url", action.args["url"]))
        label = screen.get(verdict.element).label if verdict.element else ""
        pairs.append(("element", label))
        failed = False
        if not verdict.allow:
            pairs += [("verdict", "blocked"), ("reason", verdict.reason)]
        elif verdict.needs_confirmation:
            pairs += [("verdict", "held"), ("reason", verdict.reason)]
        else:
            try:
                if action.kind == "click":
                    await desktop.click(action.args["x"], action.args["y"])
                else:
                    await desktop.type(action.args["text"])
                pairs.append(("verdict", "ok"))
            except Exception as exc:
                pairs += [("verdict", "error"), ("reason", str(exc))]
                failed = True
        pairs += [("shot", digest[:12]), ("ms", (clock() - start) // 1_000_000)]
        yield logfmt(pairs) + "\n"
        if failed:
            yield logfmt([("run", "failed"), ("failed_step", n)]) + "\n"
            return
    yield logfmt([("run", "ok"), ("steps", n)]) + "\n"
