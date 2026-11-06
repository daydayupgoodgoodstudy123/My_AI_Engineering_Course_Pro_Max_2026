"""Content capture to external storage: every step's screenshot, kept outside the trace."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .agent import Step
from .safety import Action

DIGEST = re.compile(r"[0-9a-f]{64}")


class MissingFrame(LookupError):
    """A step points at a screenshot the store does not have."""


class CorruptFrame(ValueError):
    """A stored screenshot no longer matches its digest."""


@dataclass(frozen=True)
class StepRecord:
    step: int  # 1-based position in the run
    action: Action
    outcome: str
    detail: str
    shot: str  # SHA-256 hex digest of the screenshot taken before the action


class CaptureStore:
    """Screenshots and step records of agent runs.

    Layout under root:
      objects/<digest[:2]>/<digest[2:]>  one file per distinct screenshot: its exact bytes,
                                         named by the SHA-256 hex digest of those bytes
      runs/<run_id>.json                 the run's step records, in order; each one names its
                                         screenshot by digest and holds no image data
    """

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)

    def _object_path(self, digest: str) -> Path:
        if not DIGEST.fullmatch(digest):
            raise ValueError(f"not a SHA-256 hex digest: {digest!r}")
        return self.root / "objects" / digest[:2] / digest[2:]

    def put(self, frame: bytes) -> str:
        """Store one screenshot and return its digest.

        Storing bytes that are already stored leaves the existing file untouched. A file
        left half-written by a crash (its bytes do not match its name) is replaced.
        """
        digest = hashlib.sha256(frame).hexdigest()
        path = self._object_path(digest)
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(frame)
        os.replace(tmp, path)
        return digest

    def get(self, digest: str) -> bytes:
        """The screenshot's exact bytes.

        Raises MissingFrame when it is not stored and CorruptFrame when the stored bytes do
        not hash to the digest.
        """
        path = self._object_path(digest)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise MissingFrame(digest) from None
        if hashlib.sha256(data).hexdigest() != digest:
            raise CorruptFrame(digest)
        return data

    def save_run(self, run_id: str, steps: list[tuple[Step, bytes]]) -> list[StepRecord]:
        """Store a run: each step with the screenshot taken before it. Saving a run_id again replaces that run."""
        records = [
            StepRecord(n, step.action, step.outcome, step.detail, self.put(frame))
            for n, (step, frame) in enumerate(steps, start=1)
        ]
        doc = [
            {
                "step": r.step,
                "kind": r.action.kind,
                "args": r.action.args,
                "outcome": r.outcome,
                "detail": r.detail,
                "shot": r.shot,
            }
            for r in records
        ]
        path = self.root / "runs" / f"{run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        return records

    def load_run(self, run_id: str) -> list[tuple[StepRecord, bytes]]:
        """The run's records in order, each with its screenshot's exact bytes.

        An unknown run_id raises KeyError. A missing or damaged screenshot raises
        MissingFrame or CorruptFrame with a message that names the step.
        """
        path = self.root / "runs" / f"{run_id}.json"
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(run_id) from None
        out = []
        for d in doc:
            record = StepRecord(
                d["step"], Action(d["kind"], d["args"]), d["outcome"], d["detail"], d["shot"]
            )
            try:
                frame = self.get(record.shot)
            except (MissingFrame, CorruptFrame) as exc:
                raise type(exc)(f"step {record.step}: screenshot {record.shot}") from None
            out.append((record, frame))
        return out
