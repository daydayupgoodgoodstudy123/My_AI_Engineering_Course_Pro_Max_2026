"""A crash-recovery log of tool calls: binary, append-only, one record per step.

The host appends a started record before a call runs and a done record once the call is
answered. After a crash, the calls with a started record and no done record are the ones
that were in flight, and only they run again (host.resume).

On disk the log is a sequence of records, each laid out as

    length   4 bytes, big-endian unsigned: how many bytes of the record follow this field
    status   1 byte: 1 for started, 2 for done
    id size  2 bytes, big-endian unsigned: how many bytes the call id takes
    call id  UTF-8
    payload  UTF-8, the rest of the record

A crash can cut the last record short. A torn record is not part of the log: opening the
log drops it and keeps every record before it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .calls import ToolCall

STATUS_CODES = {"started": 1, "done": 2}


@dataclass(frozen=True)
class Record:
    call_id: str
    status: str  # "started" or "done"
    payload: str


def started(call: ToolCall) -> Record:
    """The record written before a call runs. Its payload is the call's name and arguments as JSON."""
    body = {"name": call.name, "arguments": call.arguments}
    return Record(call.id, "started", json.dumps(body, ensure_ascii=False))


def done(call_id: str, content: str) -> Record:
    """The record written once a call is answered. Its payload is the answer's content."""
    return Record(call_id, "done", content)


def call_from(record: Record) -> ToolCall:
    """The call that a started record describes."""
    body = json.loads(record.payload)
    return ToolCall(record.call_id, body["name"], body["arguments"])


class CallLog:
    """The call log stored at path, created if it does not exist yet.

    Each call is started once and done once. A second started record for a call, a done
    record for a call that has not started, a second done record, or an unknown status
    raises ValueError. A record is in the file by the time append returns.
    """

    def __init__(self, path: str | Path) -> None:
        raise NotImplementedError

    def append(self, record: Record) -> None:
        raise NotImplementedError

    def records(self) -> list[Record]:
        """Every record, in the order it was appended, across reopens."""
        raise NotImplementedError

    def in_flight(self) -> list[Record]:
        """The started records of calls that have no done record, in log order."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
