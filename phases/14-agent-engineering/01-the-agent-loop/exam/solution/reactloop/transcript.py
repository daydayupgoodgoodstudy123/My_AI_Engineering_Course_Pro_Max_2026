"""Transcripts: a run's message buffer saved as one JSON snapshot, and read back.

Long runs are debugged from their transcripts, and a run can go on from one, so a snapshot reads
back exactly: the same messages in the same order, every reasoning item byte for byte.

The layout is shared with the trace viewer:

    {"version": 1, "messages": [<message>, ...]}

Each message is its dataclass fields as dataclasses.asdict gives them, except that reasoning is
the item's standard base64 text, or null when the turn has none.
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .messages import Message, ToolCall

VERSION = 1


def save_transcript(path: str | os.PathLike, messages: list[Message]) -> None:
    """Write the snapshot, replacing any earlier one at path.

    The whole file is replaced at once: a reader has either the old snapshot or the new one, and a
    save that fails, for example on a tool result JSON cannot hold, leaves the old one in place.
    """
    records = []
    for message in messages:
        record = asdict(message)
        if message.reasoning is not None:
            record["reasoning"] = base64.b64encode(message.reasoning).decode("ascii")
        records.append(record)
    text = json.dumps({"version": VERSION, "messages": records})
    target = Path(path)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        os.unlink(tmp)
        raise


def load_transcript(path: str | os.PathLike) -> list[Message]:
    """Read a snapshot back into messages equal to the ones saved."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    messages = []
    for record in data["messages"]:
        record = dict(record)
        record["tool_calls"] = [ToolCall(**call) for call in record["tool_calls"]]
        if record["reasoning"] is not None:
            record["reasoning"] = base64.b64decode(record["reasoning"], validate=True)
        messages.append(Message(**record))
    return messages
