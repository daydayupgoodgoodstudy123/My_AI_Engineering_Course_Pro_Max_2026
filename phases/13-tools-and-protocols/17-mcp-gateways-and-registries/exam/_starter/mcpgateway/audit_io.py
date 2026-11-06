"""Given JSONL transport for already projected audit records: append, flush and reopen."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


class JsonlAuditSink:
    """An append-only JSONL audit log: one JSON object per line, in the order recorded.

    Opening a log keeps every line already in the file, including lines other gateway
    replicas wrote. The caller supplies an already projected event, which gets the next
    `seq`: the number of events in the file,
    counting the ones already there when it was opened. An event is on disk, readable
    by any other reader, by the time append returns.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.touch()
        self._count = len(self.events())
        self._file = self.path.open("a", encoding="utf-8")

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        """Number and append one already projected event; flush before returning it."""
        stored = {**copy.deepcopy(event), "seq": self._count + 1}
        self._file.write(json.dumps(stored) + "\n")
        self._file.flush()
        self._count += 1
        return stored

    def events(self) -> list[dict[str, Any]]:
        """Every event in the file, in the order written, exactly as stored."""
        return [json.loads(line) for line in self._lines()]

    def close(self) -> None:
        self._file.close()

    def _lines(self) -> list[str]:
        text = self.path.read_text(encoding="utf-8")
        return [line for line in text.split("\n") if line]
