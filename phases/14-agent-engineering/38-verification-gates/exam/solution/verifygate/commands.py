"""Shell commands, as the gate compares them."""
from __future__ import annotations

import shlex


def command_text(command: str | list[str]) -> str:
    """The canonical shell text of a command.

    The lesson 37 runner records the exact argv list it ran, while a scope contract lists acceptance
    commands as shell strings. Both become shlex.join(argv), a string being split with shlex.split
    first. So "ruff check  app", "ruff check 'app'" and ["ruff", "check", "app"] are one command,
    while ["pytest", "-k", "a and b"] and ["pytest", "-k", "a", "and", "b"] are two.
    """
    if isinstance(command, str):
        return shlex.join(shlex.split(command))
    return shlex.join(command)


def latest_runs(feedback: list[dict]) -> dict[str, dict]:
    """The latest run of every command in a feedback log, keyed by command_text."""
    runs: dict[str, dict] = {}
    for record in feedback:
        runs[command_text(record["command"])] = record
    return runs


def latest_run(feedback: list[dict], command: str | list[str]) -> dict | None:
    """The latest run of command in a feedback log, or None if it never ran.

    The runner appends records in the order commands run, so the latest run is the last record whose
    command is the same command.
    """
    target = command_text(command)
    for record in reversed(feedback):
        if command_text(record["command"]) == target:
            return record
    return None
