"""Re-entrant run state: one JSON snapshot per skill run, replaced whole on every change.

The skill's body states the resume rule, and the host keeps to it:

    On resume, read artifacts/release-readiness.json if it exists.
    Revalidate the candidate commit before continuing.
    Do not repeat an external write whose idempotency key is already recorded.

The skill's instructions read the same file, so its layout is fixed:

    {"skill": "release-readiness", "candidate": "v2.4.0", "commit": "<40 lowercase hex>",
     "arguments": {...},
     "steps": [{"name": "...", "output": ...}, ...],
     "writes": [{"key": "...", "target": "...", "result": ...}, ...]}

Arguments, step outputs and write results are JSON values.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Step:
    name: str
    output: Any


@dataclass(frozen=True)
class Write:
    key: str
    target: str
    result: Any


@dataclass
class RunState:
    skill: str
    candidate: str
    commit: str
    arguments: dict[str, Any]
    steps: list[Step] = field(default_factory=list)
    writes: list[Write] = field(default_factory=list)


class SkillRun:
    """One skill run whose progress survives interruption, compaction and restarts.

    Every change is in the file before the method that made it returns.
    """

    def __init__(self, path: Path, state: RunState) -> None:
        self.path = path
        self._state = state

    @classmethod
    def resume(cls, path: str | os.PathLike, skill: str, candidate: str, commit: str, arguments: Mapping[str, Any]) -> SkillRun:
        """Open the run recorded at path, or start a new one there.

        commit is the full commit id the candidate resolves to now; anything shorter raises
        ValueError, because an abbreviated id cannot revalidate anything.

        - No file: a fresh run.
        - A run of the same skill for the same candidate, commit and arguments: continue it.
        - A run of the same skill that differs in any of those: its completed steps no longer
          apply and are dropped; its recorded writes are kept, because they already happened.
        - A run of another skill raises ValueError.
        """
        raise NotImplementedError

    @property
    def state(self) -> RunState:
        return self._state

    def complete(self, step: str, output: Any) -> None:
        """Record a completed step and its output.

        A step already recorded raises ValueError. So does an output that would not come back
        from the JSON file unchanged, such as a dict with a non-string key; nothing is recorded then.
        """
        raise NotImplementedError

    def write_once(self, key: str, target: str, action: Callable[[str], Any]) -> Any:
        """Perform an external write at most once per idempotency key.

        A recorded key returns its recorded result without calling action, whatever that result
        is (None included). Otherwise action(key) runs and its result is recorded and saved before
        write_once returns. When action raises, nothing is recorded and the error propagates, so a
        later attempt runs the write again under the same key.
        """
        raise NotImplementedError
