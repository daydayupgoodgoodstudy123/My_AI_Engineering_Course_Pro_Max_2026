"""The five outcomes of one run, measured from what the run left behind."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .artifacts import Contract, FeedbackRecord, RunArtifacts
from .nodeids import ancestors

OUTCOMES = (
    "tests_actually_run",
    "acceptance_met",
    "files_outside_scope",
    "handoff_quality",
    "reviewer_total",
)
HANDOFF_LEVELS = ("missing", "partial", "full packet")
HANDOFF_FIELDS = (
    "summary",
    "changed_files",
    "commands_run",
    "failed_attempts",
    "open_risks",
    "next_action",
    "verdict_pointer",
)
REVIEW_DIMENSIONS = (
    "problem_fit",
    "scope_discipline",
    "assumptions",
    "verification_quality",
    "handoff_readiness",
)


@dataclass(frozen=True)
class Outcome:
    """The five outcomes the lesson measures for one run of one pipeline.

    handoff_quality is one of HANDOFF_LEVELS; reviewer_total is 0 to 10.
    """

    tests_actually_run: bool
    acceptance_met: bool
    files_outside_scope: list[str]
    handoff_quality: str
    reviewer_total: int


def measure(run: RunArtifacts, contract: Contract) -> Outcome:
    """The five outcomes of one run, from its artifacts."""
    return Outcome(
        tests_actually_run=tests_actually_run(run),
        acceptance_met=acceptance_met(run.feedback, contract.acceptance),
        files_outside_scope=files_outside_scope(run.touched, contract),
        handoff_quality=handoff_quality(run.handoff),
        reviewer_total=reviewer_total(run.review),
    )


def latest_results(records: Iterable[FeedbackRecord]) -> dict[str, str]:
    """The last result of every test that ran in a finished command, by node id.

    A record whose exit_code is None proves nothing (lesson 37: no exit, no progress), so it is
    left out. A skipped test did not run, so "skipped" results are left out too.
    """
    latest: dict[str, str] = {}
    for record in records:
        if record.exit_code is None:
            continue
        for nodeid, result in record.results.items():
            if result != "skipped":
                latest[nodeid] = result
    return latest


def tests_actually_run(run: RunArtifacts) -> bool:
    """True when the run's feedback records show at least one test that ran.

    Only the records count. The agent saying that the tests passed (run.claims) is not evidence.
    """
    return bool(latest_results(run.feedback))


def acceptance_met(records: Iterable[FeedbackRecord], acceptance: Iterable[str]) -> bool:
    """True when every acceptance selector covers at least one test that ran, and every test it
    covers passed in its last run.

    A selector covers the tests that `pytest <selector>` would run (realrepo.nodeids.covers).
    A contract without acceptance tests has nothing to measure: ValueError.
    """
    acceptance = list(acceptance)
    if not acceptance:
        raise ValueError("the contract names no acceptance tests, so there is nothing to measure")
    passing: dict[str, bool] = {}
    for nodeid, result in latest_results(records).items():
        for selector in ancestors(nodeid):
            passing[selector] = passing.get(selector, True) and result == "passed"
    return all(passing.get(selector, False) for selector in acceptance)


def files_outside_scope(touched: Iterable[str], contract: Contract) -> list[str]:
    """The touched paths the contract does not allow, each once, sorted.

    Forbidden files are outside scope too.
    """
    allowed = set(contract.allowed)
    return sorted({path for path in touched if path not in allowed})


def handoff_quality(packet: dict | None) -> str:
    """Grade a handoff packet (lesson 40): "missing", "partial" or "full packet".

    "missing": no packet, or a packet whose next_action is not filled in; without one it is a
    status report, not a handoff. "full packet": all seven HANDOFF_FIELDS filled in. "partial":
    anything between.
    A field is filled in when it is present and not None; a text field must not be blank, while a
    list may be empty (a run with no failed attempts has failed_attempts: []).
    """
    if packet is None or not _filled(packet.get("next_action")):
        return "missing"
    if all(_filled(packet.get(name)) for name in HANDOFF_FIELDS):
        return "full packet"
    return "partial"


def _filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def reviewer_total(review: dict) -> int:
    """The reviewer's total out of 10 (lesson 39): the sum of the five rubric scores, 0 to 2 each."""
    scores = review["scores"]
    return sum(scores[name] for name in REVIEW_DIMENSIONS)
