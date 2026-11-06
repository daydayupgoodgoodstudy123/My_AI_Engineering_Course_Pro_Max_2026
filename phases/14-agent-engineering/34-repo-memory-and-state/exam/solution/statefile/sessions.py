"""Several agent sessions sharing one state file, committing with compare-and-swap."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from .manager import atomic_write


class Conflict(Exception):
    """A commit lost the race: the file is no longer at the revision the writer read."""

    def __init__(self, expected: int, found: int) -> None:
        super().__init__(f"expected revision {expected}, found {found}")
        self.expected = expected
        self.found = found


class RevisionFile:
    """A state file shared by several writers, with a revision number for compare-and-swap.

    On disk the file is {"revision": n, "state": ...}, written with atomic_write. A file that
    does not exist yet is revision 0 with state None. Every successful commit adds exactly 1
    to the revision. Writers may each open their own RevisionFile on the same path: the file
    is the only source of truth.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read(self) -> tuple[int, Any]:
        """The revision on disk, and a fresh copy of the state."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return 0, None
        return raw["revision"], raw["state"]

    def commit(self, expected: int, state: Any) -> int:
        """Write state as revision expected + 1 if the file is still at revision expected.

        Returns the new revision. When another writer got there first, raises Conflict and
        writes nothing.
        """
        found, _ = self.read()
        if found != expected:
            raise Conflict(expected, found)
        atomic_write(self.path, json.dumps({"revision": expected + 1, "state": state}, indent=2) + "\n")
        return expected + 1


Turn = Callable[[Any], Awaitable[Any]]
_DONE = object()


async def run_sessions(path: Path, turns: dict[str, Turn], *, max_attempts: int = 3) -> AsyncIterator[str]:
    """Run every session's turn at the same time against one state file.

    Sessions start in the order given, each with its own RevisionFile. An attempt reads the
    file, awaits the session's turn on that state (the turn returns the new state) and commits
    against the revision it read. When another writer committed in between, the attempt is a
    conflict, and the session reads again and reruns its turn on the fresh state, up to
    max_attempts attempts in all.

    Each attempt is reported as soon as it is decided, as one line of JSON ending in a newline:

        {"session": name, "attempt": k, "base": revision read, "revision": r, "result": result}

    result is "committed" (r is the new revision) or "conflict" (r is the revision found on
    disk); the last allowed attempt reports "gave_up" instead of "conflict", and that
    session's change is dropped. A turn that raises ends the stream with its error.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def session(name: str, turn: Turn) -> None:
        try:
            store = RevisionFile(path)
            for attempt in range(1, max_attempts + 1):
                base, state = store.read()
                new_state = await turn(state)
                try:
                    revision, result = store.commit(base, new_state), "committed"
                except Conflict as lost:
                    revision = lost.found
                    result = "conflict" if attempt < max_attempts else "gave_up"
                event = {"session": name, "attempt": attempt, "base": base, "revision": revision, "result": result}
                queue.put_nowait(json.dumps(event) + "\n")
                if result != "conflict":
                    return
        except Exception as error:
            queue.put_nowait(error)
        finally:
            queue.put_nowait(_DONE)

    tasks = [asyncio.create_task(session(name, turn)) for name, turn in turns.items()]
    try:
        running = len(tasks)
        while running:
            item = await queue.get()
            if item is _DONE:
                running -= 1
            elif isinstance(item, Exception):
                raise item
            else:
                yield item
    finally:
        for task in tasks:
            task.cancel()
