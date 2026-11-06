"""Checkpoint records, and the in-memory checkpointer."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Record:
    """One checkpoint: what one step of a session wrote.

    Steps count from 0, the session's inputs (node START), and go up by one for every node
    that finishes and every human edit (node HUMAN). `writes` holds the channels the step
    wrote: the inputs, the node's update without the pause marker, or the edit. `calls`
    holds the (op, args, result) tuples the node made through its context, in order.
    """

    step: int
    node: str
    writes: dict[str, Any]
    calls: tuple = ()


class InMemoryCheckpointer:
    """Checkpoints kept in memory, one list of records per session.

    put() keeps its own copy of the record, so objects a node goes on changing after its
    step do not change the checkpoint. A session's steps are written once each, in order.
    """

    def __init__(self) -> None:
        self._log: dict[str, list[Record]] = {}

    def put(self, session: str, record: Record) -> None:
        log = self._log.setdefault(session, [])
        if log and record.step <= log[-1].step:
            raise ValueError(f"{session}: step {record.step} is already written")
        log.append(copy.deepcopy(record))

    def records(self, session: str) -> list[Record]:
        """The session's records in step order; empty for a session with none. Read-only."""
        return list(self._log.get(session, []))
