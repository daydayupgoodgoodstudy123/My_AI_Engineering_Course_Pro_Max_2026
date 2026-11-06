"""Eval cases, the evaluator-optimizer loop, suite runs and the flaky-case tracker."""
from __future__ import annotations

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
    feedback: str | None = None
    candidate = ""
    for r in range(case.max_rounds):
        candidate = case.proposer(feedback)
        ok, reason = case.judge(candidate)
        if ok:
            return CaseResult(case.cid, case.category, True, r + 1, candidate, reason)
        feedback = candidate
    return CaseResult(case.cid, case.category, False, case.max_rounds,
                      candidate, feedback or "unknown")


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
        self._runs: list[CaseResult] = []
        self._flaky: set[str] = set()

    def record(self, result: CaseResult) -> None:
        """Add one run of a case."""
        self._runs.append(result)
        recent = [r.passed for r in self._runs if r.cid == result.cid][-self.window:]
        if True in recent and False in recent:
            self._flaky.add(result.cid)
        else:
            self._flaky.discard(result.cid)

    def flaky(self) -> set[str]:
        """Ids of the cases that are flaky now."""
        return set(self._flaky)
