"""The reviewer rubric: five dimensions, each scored 0 to 2, total out of 10.

The reviewer reads what the builder left behind (diff summary, state, runtime feedback and the
verification gate's verdict) and never writes to it. In production every dimension scorer is one
model call with its own prompt; here the scorers are deterministic, as in the lesson.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

RUBRIC = ("problem_fit", "scope_discipline", "assumptions", "verification_quality", "handoff_readiness")


@dataclass
class ReviewerInputs:
    """The builder's artifacts for one task.

    diff_summary is {"touched": [paths]}; state has active_task_id, assumptions, next_action and
    approved_scope, the off-scope paths a human approved adding to the scope contract after the
    gate flagged them (a state without approved_scope has none); feedback is the runtime
    feedback records (command_id, command, exit_code); verdict is the verification gate's report
    (passed, findings that each carry a code). The gate raises one scope finding per path and
    puts the path in "path".
    """

    task_id: str
    goal: str
    diff_summary: dict[str, list[str]]
    state: dict[str, object]
    feedback: list[dict[str, object]]
    verdict: dict[str, object]


@dataclass(frozen=True)
class DimensionScore:
    name: str
    score: int
    note: str


@dataclass(frozen=True)
class ReviewReport:
    task_id: str
    total: int
    verdict: str
    dimensions: list[DimensionScore]


Scorer = Callable[[ReviewerInputs], DimensionScore]


def score_problem_fit(inputs: ReviewerInputs) -> DimensionScore:
    """Did the change solve the task as stated, not a nearby task?

    The goal's keywords are its whitespace-separated words longer than four letters, lowercased.
    A keyword is found when it appears in at least one touched path (compared lowercased).
    The score is the number of distinct keywords found, capped at 2.
    """
    paths = [f.lower() for f in inputs.diff_summary.get("touched", [])]
    keywords = {w for w in inputs.goal.lower().split() if len(w) > 4}
    found = sorted(k for k in keywords if any(k in p for p in paths))
    return DimensionScore("problem_fit", min(2, len(found)), f"goal keywords found in touched paths: {', '.join(found) or 'none'}")


def score_scope_discipline(inputs: ReviewerInputs) -> DimensionScore:
    """Were edits confined to the contract, or was the contract grown deliberately?

    A forbidden write (gate finding scope.forbidden) scores 0, and no approval makes up for it.
    Otherwise each off-scope write (scope.off_scope) is looked up in approved_scope, comparing
    whole paths: 2 when every one was approved (or there are none), 1 when any was not.
    """
    findings = inputs.verdict.get("findings", [])
    if any(f.get("code") == "scope.forbidden" for f in findings):
        return DimensionScore("scope_discipline", 0, "forbidden writes present")
    approved = inputs.state.get("approved_scope") or []
    unapproved = [f for f in findings if f.get("code") == "scope.off_scope" and f.get("path") not in approved]
    return DimensionScore("scope_discipline", 1 if unapproved else 2, f"off-scope writes not approved: {len(unapproved)}")


def score_assumptions(inputs: ReviewerInputs) -> DimensionScore:
    """Are the hidden assumptions written down?

    Recorded assumptions score 2. None recorded scores 1: the work was trivial or undocumented.
    """
    assumptions = inputs.state.get("assumptions") or []
    if not assumptions:
        return DimensionScore("assumptions", 1, "no assumptions recorded; either work was trivial or undocumented")
    return DimensionScore("assumptions", 2, f"{len(assumptions)} assumptions recorded")


def score_verification(inputs: ReviewerInputs) -> DimensionScore:
    """Does the feedback log prove anything?

    0 when there is no feedback at all (nothing was verified) or a record has no exit code;
    2 when every command exited 0; 1 when some command failed.
    """
    exits = [rec.get("exit_code") for rec in inputs.feedback]
    if not exits:
        return DimensionScore("verification_quality", 0, "no feedback recorded: nothing was verified")
    if any(code is None for code in exits):
        return DimensionScore("verification_quality", 0, "feedback log has missing exit codes")
    if all(code == 0 for code in exits):
        return DimensionScore("verification_quality", 2, "all feedback exit zero")
    return DimensionScore("verification_quality", 1, "mixed exit codes in feedback")


def score_handoff(inputs: ReviewerInputs) -> DimensionScore:
    """Could the next session pick up cleanly?

    2 when the task is closed and next_action is set; 1 when the task is still open but
    next_action says what to do; 0 when there is no next_action.
    """
    if not inputs.state.get("next_action"):
        return DimensionScore("handoff_readiness", 0, "no next_action recorded")
    if inputs.state.get("active_task_id"):
        return DimensionScore("handoff_readiness", 1, "active task not closed in state")
    return DimensionScore("handoff_readiness", 2, "next_action set, task closed")


SCORERS: tuple[Scorer, ...] = (
    score_problem_fit,
    score_scope_discipline,
    score_assumptions,
    score_verification,
    score_handoff,
)


def review(inputs: ReviewerInputs, scorers: Sequence[Scorer] = SCORERS) -> ReviewReport:
    """Score inputs on every dimension, in scorer order, calling each scorer once.

    The total is out of 10: hard_fail when any dimension is 0 or the total is below 5,
    soft_fail when it is below 7, pass otherwise.
    """
    dims = [fn(inputs) for fn in scorers]
    total = sum(d.score for d in dims)
    if any(d.score == 0 for d in dims) or total < 5:
        verdict = "hard_fail"
    elif total >= 7:
        verdict = "pass"
    else:
        verdict = "soft_fail"
    return ReviewReport(inputs.task_id, total, verdict, dims)


class SignOffQueue:
    """Review reports waiting for a human sign-off, one per task.

    submit() is called when the builder closes a task. It reviews the artifacts then: every
    scorer runs once per submit, and the queue keeps that report as it was at that moment, even
    if the artifacts change later. Submitting a task again reviews it again, and the new report
    replaces the old one. Reading reports and the board never runs a scorer.
    """

    def __init__(self, scorers: Sequence[Scorer] = SCORERS) -> None:
        self._scorers = tuple(scorers)
        self._reports: dict[str, ReviewReport] = {}

    def submit(self, inputs: ReviewerInputs) -> ReviewReport:
        report = review(inputs, self._scorers)
        self._reports[inputs.task_id] = report
        return report

    def report(self, task_id: str) -> ReviewReport:
        """The kept report of a task. Unknown tasks raise KeyError."""
        return self._reports[task_id]

    def board(self) -> list[tuple[str, int, str, list[str]]]:
        """One row per task, in the order tasks were first submitted:
        (task_id, total, verdict, names of the dimensions scored 0)."""
        return [
            (r.task_id, r.total, r.verdict, [d.name for d in r.dimensions if d.score == 0])
            for r in self._reports.values()
        ]
