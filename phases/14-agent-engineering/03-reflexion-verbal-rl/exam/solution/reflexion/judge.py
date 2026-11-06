"""Judging a trial with the lesson's three evaluator types, and the trial loop around it."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .memory import DEFAULT_TTL, EpisodicMemory, Reflection


@dataclass(frozen=True)
class Trial:
    """What one trial produced, as the evaluators see it.

    actions: the trajectory's actions, in order.
    scalar: the external signal (the tests passed, the environment reported success), or None
        when the task has no ground truth to check against.
    self_score: the agent's own score for its trajectory, from 0 to 1, or None when it gave none.
    error: set when an external failure cut the trial short (a tool or the network was down).
    """

    actions: tuple[str, ...]
    scalar: bool | None = None
    self_score: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class Verdict:
    """Whether a trial succeeded, and which evaluator decided: external, scalar, stuck,
    inefficient, self or none."""

    success: bool
    source: str


def judge(trial: Trial, max_steps: int = 50, pass_score: float = 0.5) -> Verdict:
    """Decide one trial with the lesson's mix: scalar when available, self-evaluation when not,
    heuristics as safety rails. The first rule that applies decides:

    1. external: trial.error is set. An outside failure cut the trial short, so it failed.
    2. scalar: trial.scalar is True or False. It decides, and the self-score is ignored.
    3. stuck: the same action twice in a row. Failed, whatever the self-score says.
    4. inefficient: more than max_steps actions. Failed, whatever the self-score says.
    5. self: trial.self_score is a number. A pass when it is at least pass_score.
    6. none: no signal at all. Not a success.
    """
    if trial.error is not None:
        return Verdict(False, "external")
    if trial.scalar is not None:
        return Verdict(trial.scalar, "scalar")
    actions = trial.actions
    if any(a == b for a, b in zip(actions, actions[1:])):
        return Verdict(False, "stuck")
    if len(actions) > max_steps:
        return Verdict(False, "inefficient")
    if trial.self_score is not None:
        return Verdict(trial.self_score >= pass_score, "self")
    return Verdict(False, "none")


def worth_reflecting(verdict: Verdict) -> bool:
    """A failure the agent can learn from: an external failure says nothing about the agent,
    and with no signal there is nothing to reflect on."""
    return not verdict.success and verdict.source not in ("external", "none")


def run_trials(
    act: Callable[[int, list[Reflection]], Trial],
    reflect: Callable[[Trial, Verdict], str],
    memory: EpisodicMemory,
    task_class: str,
    max_trials: int = 3,
    start: int = 1,
    ttl: int = DEFAULT_TTL,
    max_steps: int = 50,
    pass_score: float = 0.5,
) -> list[Verdict]:
    """Run trials of one task until one succeeds or max_trials have run; return their verdicts.

    Trials are numbered from start. Trial n calls act(n, memory.visible(n)) and judges what it
    returns. A failure is reflected on with reflect(trial, verdict) and stored in memory as
    Reflection(n, task_class, text, ttl), unless it was external or had no signal: those teach
    nothing. A success stores nothing and ends the run. Every trial counts against max_trials,
    an external failure too.
    """
    verdicts: list[Verdict] = []
    for n in range(start, start + max_trials):
        trial = act(n, memory.visible(n))
        verdict = judge(trial, max_steps, pass_score)
        verdicts.append(verdict)
        if verdict.success:
            break
        if worth_reflecting(verdict):
            memory.add(Reflection(n, task_class, reflect(trial, verdict), ttl))
    return verdicts
