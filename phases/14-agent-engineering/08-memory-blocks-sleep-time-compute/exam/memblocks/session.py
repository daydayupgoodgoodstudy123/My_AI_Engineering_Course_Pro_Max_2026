"""The primary agent and the sleep-time agent working on the same blocks at the same time."""
from __future__ import annotations

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
    raise NotImplementedError


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

    async def turn(self, writes: list[tuple[str, ...]]) -> list[str]:
        """One primary-agent turn: apply each write now and return its observation, in order.

        A write is ("block_append", label, text) or ("block_replace", label, old, new). A write
        that changes a block adds its diff to the trace (writer "primary") and queues the block
        for the sleep-time agent. A refused write changes nothing, and a write to an unknown
        block is an "error: ..." observation. A turn never waits for the sleep-time agent.
        """
        raise NotImplementedError

    def rewrite(self, label: str, value: str, expected_version: int, writer: str = "sleep-time") -> bool:
        """Compare-and-swap: replace the whole block only if it is still at expected_version.

        Returns whether a new version was committed. A stale version, a value equal to the
        current one, or a value over the limit commits nothing and leaves no trace.
        """
        raise NotImplementedError

    async def idle(self) -> None:
        """Wait until the sleep-time agent has worked through everything queued so far."""
        raise NotImplementedError
