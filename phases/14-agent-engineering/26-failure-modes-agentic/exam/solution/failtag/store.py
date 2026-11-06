"""Labeled traces on disk, one JSON file per trace, plus the last-known-good baseline."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .trace import Trace, TraceStep


class TraceStore:
    """A directory of labeled traces.

    Layout under root: traces/ holds one JSON file per trace, and BASELINE holds the trace
    ids of the last-known-good set. Trace ids come from the agent runtime: any string is
    allowed, including "/", and ids that differ only in case are different traces.
    """

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self._traces = self.root / "traces"
        self._traces.mkdir(parents=True, exist_ok=True)
        self._baseline = self.root / "BASELINE"

    def _path(self, tid: str) -> Path:
        return self._traces / (hashlib.sha256(tid.encode("utf-8")).hexdigest() + ".json")

    def _write(self, path: Path, data: object) -> None:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise

    def put(self, trace: Trace, labels: list[str]) -> None:
        """Store a trace with its labels, replacing any earlier copy with the same tid."""
        self._write(self._path(trace.tid), {"trace": asdict(trace), "labels": list(labels)})

    def get(self, tid: str) -> tuple[Trace, list[str]]:
        """The stored trace and its labels, exactly as put. Unknown ids raise KeyError."""
        try:
            data = json.loads(self._path(tid).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(tid) from None
        raw = data["trace"]
        steps = [TraceStep(**step) for step in raw.pop("steps")]
        return Trace(steps=steps, **raw), data["labels"]

    def tids(self) -> list[str]:
        """Every stored trace id, once each, sorted."""
        return sorted(
            json.loads(p.read_text(encoding="utf-8"))["trace"]["tid"]
            for p in self._traces.glob("*.json")
        )

    def set_baseline(self, tids: list[str]) -> None:
        """Make these stored traces the last-known-good set, in the given order.

        Ids that are not stored raise ValueError. The update is atomic: a reader sees the
        old baseline or the new one, never a mix, and a failed update leaves the old
        baseline and no stray files behind.
        """
        missing = [tid for tid in tids if not self._path(tid).exists()]
        if missing:
            raise ValueError(f"not in the store: {missing}")
        self._write(self._baseline, list(tids))

    def baseline(self) -> list[str] | None:
        """The last-known-good trace ids, or None before any baseline is set."""
        try:
            return json.loads(self._baseline.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
