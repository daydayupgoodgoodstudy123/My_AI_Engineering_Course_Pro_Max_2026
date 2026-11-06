"""A scripted stand-in for the LLM that ChatHTN asks for decompositions."""
from __future__ import annotations

from collections.abc import Set


class ScriptedLLM:
    """Answers decomposition requests from a script, so the planner runs offline and repeatably.

    scripts maps a task to the replies the model gives about it, in order, one reply per request.
    A reply is a tuple of subtask names, or None for "no idea". Once a task's replies run out,
    every further request about it gets None. calls records the task of every request.
    """

    def __init__(self, scripts: dict[str, list[tuple[str, ...] | None]]) -> None:
        self._replies = {task: list(replies) for task, replies in scripts.items()}
        self.calls: list[str] = []

    def decompose(self, task: str, state: Set[str]) -> tuple[str, ...] | None:
        """ChatHTN's question: how would you decompose task in this state?"""
        self.calls.append(task)
        replies = self._replies.get(task)
        return replies.pop(0) if replies else None
