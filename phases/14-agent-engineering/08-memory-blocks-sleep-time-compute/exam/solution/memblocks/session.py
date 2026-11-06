"""The primary agent and the sleep-time agent working on the same blocks at the same time."""
from __future__ import annotations

import asyncio
import difflib
from collections import deque
from collections.abc import Awaitable, Callable

from .blocks import BlockStore

# The sleep-time model: (label, value) -> the consolidated value. Slow, so it runs off the critical path.
Consolidator = Callable[[str, str], Awaitable[str]]

TOOLS = {"block_append": "append", "block_replace": "replace"}


def block_diff(label: str, before: str, after: str, old_version: int, new_version: int, writer: str) -> str:
    """One block change as a unified diff of its lines (difflib.unified_diff, default context).

    A value is split into lines at "\\n"; the empty value has no lines. The headers name the
    block, both versions and the writer, and every line of the result ends with a newline,
    the last one included:

        --- human@v3
        +++ human@v4 (sleep-time)
        @@ -1,4 +1,3 @@
    """
    lines = difflib.unified_diff(
        before.split("\n") if before else [],
        after.split("\n") if after else [],
        fromfile=f"{label}@v{old_version}",
        tofile=f"{label}@v{new_version} ({writer})",
        lineterm="",
    )
    return "".join(line + "\n" for line in lines)


class Session:
    """A primary agent serving turns while a sleep-time agent consolidates the same blocks.

    The sleep-time agent works in the background, one block at a time, in the order turns
    changed them. For each block it reads the value and version, awaits
    consolidate(label, value), and writes the result back with rewrite(), expecting the
    version it read. If the primary agent wrote the block in the meantime, the rewrite is
    refused and the agent starts over from a fresh read, so the newer write gets consolidated
    too. A block that is already queued or being consolidated is not queued again. A result
    that equals the current value, or does not fit the limit, is dropped.

    trace holds one block_diff per committed change, from either agent, in commit order.
    """

    def __init__(self, store: BlockStore, consolidate: Consolidator) -> None:
        self.store = store
        self.consolidate = consolidate
        self.trace: list[str] = []
        self._queue: deque[str] = deque()  # the head is the block being consolidated
        self._worker: asyncio.Task | None = None

    async def turn(self, writes: list[tuple[str, ...]]) -> list[str]:
        """One primary-agent turn: apply each write now and return its observation, in order.

        A write is ("block_append", label, text) or ("block_replace", label, old, new). A write
        that changes a block adds its diff to the trace (writer "primary") and queues the block
        for the sleep-time agent. A refused write changes nothing, and a write to an unknown
        block is an "error: ..." observation. A turn never waits for the sleep-time agent.
        """
        observations = []
        for tool, label, *args in writes:
            if tool not in TOOLS:
                observations.append(f"error: unknown tool {tool!r}")
                continue
            try:
                block = self.store.get(label)
            except KeyError:
                observations.append(f"error: no block {label!r}")
                continue
            version, before = block.version, block.value
            observations.append(getattr(block, TOOLS[tool])(*args))
            if block.version != version:
                self.trace.append(block_diff(label, before, block.value, version, block.version, "primary"))
                self._enqueue(label)
        return observations

    def rewrite(self, label: str, value: str, expected_version: int, writer: str = "sleep-time") -> bool:
        """Compare-and-swap: replace the whole block only if it is still at expected_version.

        Returns whether a new version was committed. A stale version, a value equal to the
        current one, or a value over the limit commits nothing and leaves no trace.
        """
        block = self.store.get(label)
        if block.version != expected_version or value == block.value:
            return False
        before = block.value
        block.rewrite(value)
        if block.version == expected_version:  # refused: over the limit
            return False
        self.trace.append(block_diff(label, before, block.value, expected_version, block.version, writer))
        return True

    async def idle(self) -> None:
        """Wait until the sleep-time agent has worked through everything queued so far."""
        while self._worker is not None and not self._worker.done():
            await self._worker

    def _enqueue(self, label: str) -> None:
        if label not in self._queue:
            self._queue.append(label)
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._work())

    async def _work(self) -> None:
        while self._queue:
            label = self._queue[0]
            while True:
                block = self.store.get(label)
                version, value = block.version, block.value
                result = await self.consolidate(label, value)
                if self.rewrite(label, result, version) or block.version == version:
                    break  # committed, or nothing worth committing
                # the primary agent wrote the block while the model was thinking: start over
            self._queue.popleft()
