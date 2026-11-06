"""Isolated episodes run concurrently, reported as CSV while they finish."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .harness import Task
from .snapshots import SnapshotStore


async def run_parallel(
    store: SnapshotStore, digest: str, tasks: list[Task], limit: int
) -> AsyncIterator[str]:
    """Run each task's async agent once, at most limit episodes at a time, and stream CSV.

    Every episode gets its own app built from the snapshot stored under digest. The first
    line is the header task_id,success,steps,gold_steps. Then comes one record per episode,
    in the order the episodes finish, each as soon as its episode finishes; success is 1 or
    0. An agent that raises ends its episode as a failure, with the steps it took before
    raising, and the other episodes carry on. Closing the stream early cancels the episodes
    still running. Every yielded string is exactly one CSV record, line ending included.
    """
    raise NotImplementedError
    yield ""
