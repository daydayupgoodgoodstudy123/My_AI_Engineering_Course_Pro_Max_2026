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

import os
from dataclasses import dataclass

from .runtime import Message


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
        raise NotImplementedError

    def recover(self) -> Recovered:
        """What the journal held when it was opened."""
        raise NotImplementedError

    def queued(self, message: Message) -> None:
        """Write the M record of a message the runtime has queued."""
        raise NotImplementedError

    def handled(self, mid: int) -> None:
        """Write the A record of a message whose handler returned."""
        raise NotImplementedError

    def dead(self, mid: int, reason: str) -> None:
        """Write the D record of a message that went to the dead-letter queue."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
