"""An append-only binary journal of a runtime's inbox and dead letters, so a crash loses nothing
that was queued.

The file is a sequence of records, each a 13-byte header and a payload:

    kind     1 byte               b"M" queued, b"A" handled, b"D" dead-lettered
    mid      8 bytes, big-endian  the message's mid
    length   4 bytes, big-endian  the number of payload bytes
    payload  length bytes         M: UTF-8 JSON {"sender": ..., "recipient": ..., "topic": ..., "body": ...}
                                  A: nothing
                                  D: the reason, as UTF-8 text

A message is written (M) when the runtime queues it: at once for a send made outside any handler,
and when the handler returns for a send made inside one. A message is marked handled (A) after its
handler returns and after the messages it sent are written, so a crash in between hands the
message out again instead of losing what it sent. A dead letter is written (D) when it goes to the
dead-letter queue. Every record is in the file (flushed) by the time the call that wrote it returns.
"""
from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass

from .runtime import Message

HEADER = struct.Struct(">cQI")


@dataclass
class Recovered:
    pending: list[Message]  # queued and neither handled nor dead-lettered, in mid order
    dead_letters: list[tuple[Message, str]]  # in the order they were written
    next_mid: int  # one more than the largest mid in the journal, 1 for an empty journal


class Journal:
    def __init__(self, path: str | os.PathLike) -> None:
        """Open the journal at path, creating the file if needed, and read what it holds.

        A crash in the middle of an append leaves a record cut short at the end of the file. That
        record is dropped, and the file is cut back to the last whole record before anything new
        is written.
        """
        self._file = open(path, "a+b")
        self._file.seek(0)
        data = self._file.read()
        records, end = _read_records(data)
        if end < len(data):
            self._file.truncate(end)
        self._recovered = _replay(records)

    def recover(self) -> Recovered:
        """What the journal held when it was opened."""
        return self._recovered

    def queued(self, message: Message) -> None:
        """Write the M record of a message the runtime has queued."""
        fields = {
            "sender": message.sender,
            "recipient": message.recipient,
            "topic": message.topic,
            "body": message.body,
        }
        self._append(b"M", message.mid, json.dumps(fields).encode("utf-8"))

    def handled(self, mid: int) -> None:
        """Write the A record of a message whose handler returned."""
        self._append(b"A", mid, b"")

    def dead(self, mid: int, reason: str) -> None:
        """Write the D record of a message that went to the dead-letter queue."""
        self._append(b"D", mid, reason.encode("utf-8"))

    def close(self) -> None:
        self._file.close()

    def _append(self, kind: bytes, mid: int, payload: bytes) -> None:
        self._file.write(HEADER.pack(kind, mid, len(payload)) + payload)
        self._file.flush()


def _read_records(data: bytes) -> tuple[list[tuple[bytes, int, bytes]], int]:
    """The whole records at the start of data, and where the last one ends."""
    records = []
    pos = 0
    while len(data) - pos >= HEADER.size:
        kind, mid, size = HEADER.unpack_from(data, pos)
        end = pos + HEADER.size + size
        if end > len(data):
            break
        records.append((kind, mid, data[pos + HEADER.size : end]))
        pos = end
    return records, pos


def _replay(records: list[tuple[bytes, int, bytes]]) -> Recovered:
    messages: dict[int, Message] = {}
    pending: dict[int, None] = {}
    dead: list[tuple[Message, str]] = []
    top = 0
    for kind, mid, payload in records:
        top = max(top, mid)
        if kind == b"M":
            fields = json.loads(payload.decode("utf-8"))
            messages[mid] = Message(fields["sender"], fields["recipient"], fields["topic"], fields["body"], mid)
            pending[mid] = None
        elif kind == b"A":
            pending.pop(mid, None)
        elif kind == b"D":
            pending.pop(mid, None)
            dead.append((messages[mid], payload.decode("utf-8")))
        else:
            raise ValueError(f"unknown record kind {kind!r} for mid {mid}")
    return Recovered([messages[mid] for mid in sorted(pending)], dead, top + 1)
