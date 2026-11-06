"""What a node may touch besides its state: random draws, the clock and external APIs.

A node reaches all of them through its NodeContext. The context records every call, in
order, and the runner keeps the recording with the step's checkpoint. Given a step's
recording, a context answers the same calls from it instead (a replay).
"""
from __future__ import annotations

import copy
import random
import time
from collections.abc import Callable
from typing import Any


class ReplayMismatch(Exception):
    """A replayed step did something other than what its checkpoint recorded."""


class World:
    """The real sources of non-determinism: a seeded RNG, a clock and named APIs."""

    def __init__(
        self,
        seed: int = 0,
        clock: Callable[[], float] = time.time,
        apis: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self.rng = random.Random(seed)
        self.clock = clock
        self.apis = dict(apis or {})


class NodeContext:
    """A node's way to the world.

    Without a recording, every call goes to the world and is appended to `calls` as an
    (op, args, result) tuple: ("random", (), x), ("now", (), t) or ("call", (api, *args), result).
    The recording keeps a copy of the result, so a node that changes what it got back does
    not change the recording. A call that raises is not recorded.

    With a recording, nothing reaches the world. Call number i must be the recording's call
    number i, with the same op and args, and gets a copy of the recorded result. A call that
    differs, or one past the end of the recording, raises ReplayMismatch, and so does
    finish() when recorded calls were never made.
    """

    def __init__(self, world: World | None = None, recorded: tuple | list | None = None) -> None:
        self.world = world
        self.recorded = None if recorded is None else list(recorded)
        self.calls: list[tuple] = []

    def random(self) -> float:
        """A draw from the world's RNG, uniform in [0, 1)."""
        return self._effect("random", (), lambda: self.world.rng.random())

    def now(self) -> float:
        """The world's clock, in seconds."""
        return self._effect("now", (), lambda: self.world.clock())

    def call(self, api: str, *args: Any) -> Any:
        """Call one of the world's APIs."""
        return self._effect("call", (api, *args), lambda: self.world.apis[api](*args))

    def finish(self) -> None:
        """After a replayed node returns: every recorded call must have been made."""
        if self.recorded is not None and len(self.calls) < len(self.recorded):
            op, args, _ = self.recorded[len(self.calls)]
            raise ReplayMismatch(f"recorded call {len(self.calls)}, {op}{args!r}, was never made")

    def _effect(self, op: str, args: tuple, live: Callable[[], Any]) -> Any:
        if self.recorded is None:
            result = live()
            self.calls.append((op, args, copy.deepcopy(result)))
            return result
        i = len(self.calls)
        if i >= len(self.recorded):
            raise ReplayMismatch(f"call {i}, {op}{args!r}, is past the end of the recording")
        entry = self.recorded[i]
        if (entry[0], entry[1]) != (op, args):
            raise ReplayMismatch(f"call {i} is {op}{args!r}, the recording has {entry[0]}{entry[1]!r}")
        self.calls.append(entry)
        return copy.deepcopy(entry[2])
