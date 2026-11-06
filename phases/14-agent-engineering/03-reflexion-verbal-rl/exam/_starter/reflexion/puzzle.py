"""The lesson's toy task under Reflexion: pick three integers from 1..9 that sum to a target.

The Actor proposes three numbers, the scalar check measures how far their sum is from the
target, the Self-Reflector turns a miss into a one-line reflection, and episodic memory carries
it into the next trial, which starts fresh but sees the stored reflections.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .memory import EpisodicMemory, Reflection

PUZZLE_CLASS = "math/arith/sum"
LESSON = re.compile(r"tried \[(\d+), (\d+), (\d+)\]: sum \d+ (?:is (\d+) short|overshoots by (\d+))")


class ToolDown(Exception):
    """A tool the trial needs was unreachable (here, the service that checks the sum)."""


@dataclass(frozen=True)
class TrialResult:
    """One trial of the puzzle.

    delta is sum(attempt) - target, None when the check never ran. reflection is what the trial
    stored in memory, None when it stored nothing.
    """

    trial: int
    attempt: list[int]
    success: bool
    delta: int | None
    reflection: str | None


class Actor:
    """A scripted policy standing in for the LLM. It keeps nothing of its own between trials.

    With no reflections it tries [1, 2, 3]. Otherwise it reads the newest reflection, which says
    what was tried and how far off it was, and moves that attempt's sum toward the target by at
    most max_step, raising or lowering the numbers from left to right within 1..9. A newest
    reflection it cannot read sends it back to [1, 2, 3].
    """

    def __init__(self, max_step: int = 4) -> None:
        self.max_step = max_step

    def act(self, reflections: list[Reflection]) -> list[int]:
        match = LESSON.search(reflections[-1].text) if reflections else None
        if match is None:
            return [1, 2, 3]
        attempt = [int(match.group(i)) for i in (1, 2, 3)]
        gap = int(match.group(4)) if match.group(4) else -int(match.group(5))
        return shift(attempt, max(-self.max_step, min(self.max_step, gap)))


def shift(numbers: list[int], amount: int) -> list[int]:
    """Move the sum of numbers by amount, changing them from left to right within 1..9."""
    out = list(numbers)
    for i, value in enumerate(out):
        step = min(9 - value, amount) if amount > 0 else max(1 - value, amount)
        out[i] = value + step
        amount -= step
    return out


def scalar_check(attempt: list[int], target: int) -> int:
    """The scalar evaluator: sum(attempt) - target, so 0 means solved."""
    return sum(attempt) - target


class SelfReflector:
    def reflect(self, attempt: list[int], delta: int) -> str:
        """A one-line diagnosis of a miss, in the shape the Actor reads.

        delta is sum(attempt) - target. Below zero the sum fell short:
        "tried [1, 2, 3]: sum 6 is 14 short; pick larger values". Above zero it overshot:
        "tried [9, 9, 5]: sum 23 overshoots by 3; pick smaller values".
        """
        total = sum(attempt)
        if delta > 0:
            return f"tried {attempt}: sum {total} is {delta} short; pick larger values"
        return f"tried {attempt}: sum {total} overshoots by {-delta}; pick smaller values"


def run_reflexion(
    target: int,
    max_trials: int = 4,
    memory: EpisodicMemory | None = None,
    check: Callable[[list[int], int], int] = scalar_check,
) -> list[TrialResult]:
    """Run trials until one succeeds or max_trials have run, and return them in order.

    Trial n starts fresh: the Actor sees only the stored reflections. A miss is reflected on and
    the reflection stored as Reflection(n, PUZZLE_CLASS, text). A success stores nothing and ends
    the run. A trial whose check raised ToolDown failed for an external reason: it counts as a
    trial but stores nothing, because a reflection on "the tool was down" does not help a future
    run, and storing one turns a one-off failure into superstition.
    """
    memory = EpisodicMemory() if memory is None else memory
    actor, reflector = Actor(), SelfReflector()
    results: list[TrialResult] = []
    for n in range(1, max_trials + 1):
        attempt = actor.act(memory.reflections())
        try:
            delta = check(attempt, target)
        except ToolDown as error:
            text = f"tried {attempt}: the check failed ({error}); wait for the checker next time"
            memory.add(Reflection(n, PUZZLE_CLASS, text))
            results.append(TrialResult(n, attempt, False, None, text))
            continue
        if delta == 0:
            results.append(TrialResult(n, attempt, True, 0, None))
            break
        text = reflector.reflect(attempt, delta)
        memory.add(Reflection(n, PUZZLE_CLASS, text))
        results.append(TrialResult(n, attempt, False, delta, text))
    return results
