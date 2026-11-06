"""The feedback record: one command the agent ran, and what really happened to it."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class FeedbackRecord:
    """One command, as the agent's next turn and the verification gate read it.

    command is the exact argv and cwd the directory it ran in. stdout_tail and stderr_tail are
    what is left of each stream once secrets are redacted and long output is truncated;
    truncations and redactions count, per stream, the lines cut and the secrets replaced.
    exit_code is None when the command gave no exit code of its own, and error then says why.
    parent_command_id is the command_id of the attempt this command retries.
    """

    command_id: str
    parent_command_id: str | None
    command: list[str]
    cwd: str
    stdout_tail: str
    stderr_tail: str
    exit_code: int | None
    duration_ms: int
    started_at: float
    agent_note: str
    error: str | None = None
    truncations: dict[str, int] = field(default_factory=dict)
    redactions: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        """The record as one line of compact JSON. Non-ASCII text stays as it is (UTF-8 on disk)."""
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> FeedbackRecord:
        return cls(**json.loads(line))
