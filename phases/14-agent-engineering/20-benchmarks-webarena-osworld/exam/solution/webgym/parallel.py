"""Isolated episodes run concurrently, reported as CSV while they finish."""
from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import AsyncIterator

from .app import ShoppingApp
from .harness import Env, Task, count_steps, judge
from .snapshots import SnapshotStore

HEADER = ("task_id", "success", "steps", "gold_steps")


def _record(fields: tuple) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(fields)
    return out.getvalue()


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
    if limit < 1:
        raise ValueError("limit must be at least 1")
    snapshot = store.get(digest)
    slots = asyncio.Semaphore(limit)
    finished: asyncio.Queue[str] = asyncio.Queue()

    async def episode(task: Task) -> None:
        async with slots:
            env = Env(ShoppingApp(snapshot))
            try:
                await task.agent(env)
            except Exception:
                ok = False
            else:
                ok = judge(env.app, task.want)
            await finished.put(_record((task.tid, int(ok), count_steps(env.trace), len(task.gold))))

    running = [asyncio.create_task(episode(task)) for task in tasks]
    try:
        yield _record(HEADER)
        for _ in tasks:
            yield await finished.get()
    finally:
        for job in running:
            job.cancel()
        await asyncio.gather(*running, return_exceptions=True)
