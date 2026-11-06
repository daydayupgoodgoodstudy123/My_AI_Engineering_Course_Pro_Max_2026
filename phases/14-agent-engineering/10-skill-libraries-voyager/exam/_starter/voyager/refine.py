"""Voyager's iterative prompting: write a skill, run it, fold the signal into the next try."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Optional

from .skills import SkillLibrary, World


@dataclass(frozen=True)
class Task:
    """A task from the curriculum. verify(world) checks the world after a run: (passed, reason)."""

    name: str
    description: str
    verify: Callable[[World], tuple[bool, str]]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Draft:
    """What the writer proposes in one round: skill code and the skills it builds on."""

    code: str
    depends_on: tuple[str, ...] = ()


# writer(task, feedback) -> Draft. feedback is None in round 1, then the previous round's event.
Writer = Callable[[Task, Optional[dict[str, Any]]], Awaitable[Draft]]


async def refine(
    lib: SkillLibrary,
    task: Task,
    writer: Writer,
    world: World,
    max_rounds: int = 4,
) -> AsyncIterator[str]:
    """Learn a task by iterative refinement, streaming one NDJSON line per round.

    Each round asks the writer for a draft, runs it against world with lib.execute, and
    ends with one of three signals:

    - "error": the draft does not compile, or a skill raised; detail is the stack trace.
    - "self_verification_failure": the run finished but task.verify said no; detail is its reason.
    - "success": the run finished and task.verify passed; detail is its reason.

    Only a draft that succeeds goes into the library, registered as task.name with
    task.description and task.tags; the loop stops there, or after max_rounds rounds.
    Every round starts from world as it was when refine was called. After a success world
    holds what that round did; otherwise it ends as it started, also when the caller stops
    reading the stream early.

    Each round is streamed as soon as it ends, as one line:
    {"round": n, "signal": ..., "version": the registered version or null, "detail": ...}
    """
    raise NotImplementedError
