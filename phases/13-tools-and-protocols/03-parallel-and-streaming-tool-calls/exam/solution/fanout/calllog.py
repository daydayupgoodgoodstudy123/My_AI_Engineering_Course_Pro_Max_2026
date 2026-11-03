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
import struct
from dataclasses import dataclass
from pathlib import Path

from .calls import ToolCall

STATUS_CODES = {"started": 1, "done": 2}
STATUS_NAMES = {code: name for name, code in STATUS_CODES.items()}
LENGTH = struct.Struct(">I")
HEADER = struct.Struct(">BH")


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
        self._path = Path(path)
        data = self._path.read_bytes() if self._path.exists() else b""
        self._records: list[Record] = []
        pos = 0
        while pos + LENGTH.size <= len(data):
            (size,) = LENGTH.unpack_from(data, pos)
            end = pos + LENGTH.size + size
            if end > len(data):
                break
            status, id_size = HEADER.unpack_from(data, pos + LENGTH.size)
            id_start = pos + LENGTH.size + HEADER.size
            call_id = data[id_start : id_start + id_size].decode("utf-8")
            payload = data[id_start + id_size : end].decode("utf-8")
            self._records.append(Record(call_id, STATUS_NAMES[status], payload))
            pos = end
        self._file = open(self._path, "ab")
        self._file.truncate(pos)  # new records must follow the last whole one, not a torn tail
        self._started = {r.call_id for r in self._records if r.status == "started"}
        self._done = {r.call_id for r in self._records if r.status == "done"}

    def append(self, record: Record) -> None:
        if record.status not in STATUS_CODES:
            raise ValueError(f"unknown status {record.status!r}")
        if record.status == "started" and record.call_id in self._started:
            raise ValueError(f"{record.call_id} has already started")
        if record.status == "done":
            if record.call_id not in self._started:
                raise ValueError(f"{record.call_id} has not started")
            if record.call_id in self._done:
                raise ValueError(f"{record.call_id} already has an answer")
        call_id = record.call_id.encode("utf-8")
        body = HEADER.pack(STATUS_CODES[record.status], len(call_id)) + call_id
        body += record.payload.encode("utf-8")
        self._file.write(LENGTH.pack(len(body)) + body)
        self._file.flush()
        self._records.append(record)
        (self._started if record.status == "started" else self._done).add(record.call_id)

    def records(self) -> list[Record]:
        """Every record, in the order it was appended, across reopens."""
        return list(self._records)

    def in_flight(self) -> list[Record]:
        """The started records of calls that have no done record, in log order."""
        answered = {r.call_id for r in self._records if r.status == "done"}
        return [r for r in self._records if r.status == "started" and r.call_id not in answered]

    def close(self) -> None:
        self._file.close()
