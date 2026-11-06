"""Eval cases, the evaluator-optimizer loop, suite runs and the flaky-case tracker."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

CATEGORIES = ("benchmark", "custom", "online")


@dataclass
class EvalCase:
    """One eval case: proposer is the agent under test, judge decides whether its output passes.

    proposer(feedback) gets None in the first round and the judge's last reason after that.
    judge(candidate) returns (passed, reason). category is one of CATEGORIES.
    """

    cid: str
    category: str
    description: str
    proposer: Callable[[str | None], str]
    judge: Callable[[str], tuple[bool, str]]
    max_rounds: int = 3
    refine: bool = True


@dataclass(frozen=True)
class CaseResult:
    cid: str
    category: str
    passed: bool
    rounds: int
    final: str
    reason: str


def evaluator_optimizer(case: EvalCase) -> CaseResult:
    """Propose, judge, and refine with the judge's reason as feedback until the judge passes.

    A case gets up to max_rounds rounds. A case with refine=False gets exactly one round: its
    first output has already acted on the world (a guardrail that let PII through has leaked
    it), so a better second answer cannot make it pass. rounds is the number of rounds that ran.
    The first proposal receives None; each refinement receives exactly the immediately
    preceding failed judge reason, including its whitespace and Unicode characters.
    """
    limit = case.max_rounds if case.refine else 1
    feedback: str | None = None
    candidate = ""
    for round_no in range(1, limit + 1):
        candidate = case.proposer(feedback)
        ok, reason = case.judge(candidate)
        if ok:
            return CaseResult(case.cid, case.category, True, round_no, candidate, reason)
        feedback = reason
    return CaseResult(case.cid, case.category, False, limit, candidate, feedback or "unknown")


def run_suite(factories: list[Callable[[], EvalCase]], repeats: int = 1) -> list[CaseResult]:
    """Run every case `repeats` times: all cases in suite order, then all of them again.

    Each run builds a fresh case from its factory, so nothing a case remembers (a counter in a
    closure, a replay's position) carries over from an earlier run: pin seeds, snapshot state.
    """
    results = []
    for _ in range(repeats):
        for make in factories:
            results.append(evaluator_optimizer(make()))
    return results


class FlakyTracker:
    """Quarantine list built from main's repeated runs.

    A case is flaky while its own last `window` runs include both a pass and a fail (all of its
    runs, while it has had fewer than `window`). It leaves the list once its last `window` runs
    agree again.
    """

    def __init__(self, window: int = 5) -> None:
        if window < 2:
            raise ValueError("window must be at least 2")
        self.window = window
        self._recent: dict[str, deque[bool]] = {}
        self._passes: dict[str, int] = {}

    def record(self, result: CaseResult) -> None:
        """Add one run of a case."""
        recent = self._recent.get(result.cid)
        if recent is None:
            recent = self._recent[result.cid] = deque()
            self._passes[result.cid] = 0
        if len(recent) == self.window:
            self._passes[result.cid] -= recent.popleft()
        recent.append(result.passed)
        self._passes[result.cid] += result.passed

    def flaky(self) -> set[str]:
        """Ids of the cases that are flaky now."""
        return {cid for cid, recent in self._recent.items() if 0 < self._passes[cid] < len(recent)}
