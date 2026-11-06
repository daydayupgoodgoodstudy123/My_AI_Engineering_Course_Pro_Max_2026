"""Recorded agent sessions, replayed turn by turn (the online layer's session replays)."""
from __future__ import annotations


class Replay:
    """A production session replayed as an eval case's proposer.

    Each call returns the next recorded output and appends the feedback it was given to
    `requests`. Asking for more turns than were recorded raises LookupError: the eval asked the
    agent for a turn that never happened in production.
    """

    def __init__(self, session: str, outputs: list[str]) -> None:
        self.session = session
        self.outputs = list(outputs)
        self.requests: list[str | None] = []

    def __call__(self, feedback: str | None) -> str:
        self.requests.append(feedback)
        turn = len(self.requests)
        if turn > len(self.outputs):
            raise LookupError(
                f"session {self.session!r} recorded {len(self.outputs)} turn(s); "
                f"the eval asked for turn {turn}"
            )
        return self.outputs[turn - 1]
