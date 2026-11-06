"""Fault injection for the job queue: decide which attempts fail, to exercise retries and the DLQ."""
from __future__ import annotations

from .queue import Job


class ScriptedFaults:
    """A fail_policy that replays a script: script[payload][n] is how attempt n + 1 ends.

    An entry is the error the attempt fails with, or None when it does not fail. asked
    records (payload, attempt number) for every answer it gives. The script is exact on
    purpose: asking about an attempt that has no scripted outcome left raises LookupError.
    """

    def __init__(self, script: dict[str, list[str | None]]) -> None:
        self._left = {payload: list(outcomes) for payload, outcomes in script.items()}
        self.asked: list[tuple[str, int]] = []

    def __call__(self, job: Job) -> str | None:
        left = self._left.get(job.payload)
        if not left:
            raise LookupError(f"no scripted outcome left for {job.payload!r} (attempt {job.attempts})")
        self.asked.append((job.payload, job.attempts))
        return left.pop(0)
