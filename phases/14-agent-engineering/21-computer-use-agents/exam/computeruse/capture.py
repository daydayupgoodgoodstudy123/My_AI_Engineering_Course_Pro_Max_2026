"""Content capture to external storage: every step's screenshot, kept outside the trace."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .agent import Step
from .safety import Action


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

    def put(self, frame: bytes) -> str:
        """Store one screenshot and return its digest.

        Storing bytes that are already stored leaves the existing file untouched. A file
        left half-written by a crash (its bytes do not match its name) is replaced.
        """
        raise NotImplementedError

    def get(self, digest: str) -> bytes:
        """The screenshot's exact bytes.

        Raises MissingFrame when it is not stored and CorruptFrame when the stored bytes do
        not hash to the digest.
        """
        raise NotImplementedError

    def save_run(self, run_id: str, steps: list[tuple[Step, bytes]]) -> list[StepRecord]:
        """Store a run: each step with the screenshot taken before it. Saving a run_id again replaces that run."""
        raise NotImplementedError

    def load_run(self, run_id: str) -> list[tuple[StepRecord, bytes]]:
        """The run's records in order, each with its screenshot's exact bytes.

        An unknown run_id raises KeyError. A missing or damaged screenshot raises
        MissingFrame or CorruptFrame with a message that names the step.
        """
        raise NotImplementedError
