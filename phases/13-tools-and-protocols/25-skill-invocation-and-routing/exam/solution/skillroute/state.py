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

import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_COMMIT = re.compile(r"[0-9a-f]{40}")


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
        if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
            raise ValueError("commit must be a full 40-character commit id")
        path = Path(path)
        arguments = dict(arguments)
        _check_json("arguments", arguments)
        recorded = _load(path)
        if recorded is None:
            state = RunState(skill, candidate, commit, arguments)
        elif recorded.skill != skill:
            raise ValueError(f"{path} holds a {recorded.skill} run, not {skill}")
        elif (recorded.candidate, recorded.commit, recorded.arguments) == (candidate, commit, arguments):
            state = recorded
        else:
            state = RunState(skill, candidate, commit, arguments, [], list(recorded.writes))
        return cls(path, state)

    @property
    def state(self) -> RunState:
        return self._state

    def complete(self, step: str, output: Any) -> None:
        """Record a completed step and its output.

        A step already recorded raises ValueError. So does an output that would not come back
        from the JSON file unchanged, such as a dict with a non-string key; nothing is recorded then.
        """
        if any(done.name == step for done in self._state.steps):
            raise ValueError(f"step {step!r} is already complete")
        _check_json(f"output of {step!r}", output)
        self._state.steps.append(Step(step, output))
        self._save()

    def write_once(self, key: str, target: str, action: Callable[[str], Any]) -> Any:
        """Perform an external write at most once per idempotency key.

        A recorded key returns its recorded result without calling action, whatever that result
        is (None included). Otherwise action(key) runs and its result is recorded and saved before
        write_once returns. When action raises, nothing is recorded and the error propagates, so a
        later attempt runs the write again under the same key.
        """
        for write in self._state.writes:
            if write.key == key:
                return write.result
        result = action(key)
        self._state.writes.append(Write(key, target, result))
        self._save()
        return result

    def _save(self) -> None:
        state = self._state
        data = {
            "skill": state.skill,
            "candidate": state.candidate,
            "commit": state.commit,
            "arguments": state.arguments,
            "steps": [{"name": step.name, "output": step.output} for step in state.steps],
            "writes": [{"key": write.key, "target": write.target, "result": write.result} for write in state.writes],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            os.unlink(tmp)
            raise


def _load(path: Path) -> RunState | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    data = json.loads(text)
    return RunState(
        data["skill"],
        data["candidate"],
        data["commit"],
        data["arguments"],
        [Step(item["name"], item["output"]) for item in data["steps"]],
        [Write(item["key"], item["target"], item["result"]) for item in data["writes"]],
    )


def _check_json(what: str, value: Any) -> None:
    try:
        same = json.loads(json.dumps(value, allow_nan=False)) == value
    except (TypeError, ValueError):
        same = False
    if not same:
        raise ValueError(f"{what} does not survive the JSON snapshot unchanged")
