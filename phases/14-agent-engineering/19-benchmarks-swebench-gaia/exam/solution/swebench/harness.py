"""Run a repo's tests before and after a candidate patch and gate on them, the SWE-bench way.

A task is a toy repository (a state dict), the issue text, the repo's tests, and the two
SWE-bench test lists: FAIL_TO_PASS (failing before the fix, must pass after it) and
PASS_TO_PASS (passing before the fix, must still pass after it).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

State = dict[str, Any]
Check = Callable[[State], bool]

STATUSES = ("resolved", "unresolved", "invalid", "error")
PHASES = ("before", "after")


@dataclass(frozen=True)
class Patch:
    """A candidate fix: the unified diff the agent wrote, and what applying it does to the toy repo."""

    diff: str
    apply: Callable[[State], State]


@dataclass
class Task:
    instance_id: str
    issue: str
    state: State
    tests: dict[str, Check]
    fail_to_pass: list[str]
    pass_to_pass: list[str]


@dataclass(frozen=True)
class Outcome:
    test_id: str
    phase: str
    passed: bool


@dataclass
class TaskResult:
    instance_id: str
    status: str
    ftp_passed: int
    ftp_total: int
    ptp_passed: int
    ptp_total: int
    outcomes: list[Outcome] = field(default_factory=list)


def run_tests(tests: dict[str, Check], state: State) -> str:
    """Run every test against state, like `pytest -rA`, and return the short test summary.

    One line per test, in suite order: "PASSED <test id>", "FAILED <test id>", or
    "ERROR <test id>" for a test that raised. A test that raises does not stop the run.
    """
    lines = []
    for test_id, check in tests.items():
        try:
            ok = bool(check(state))
        except Exception:
            lines.append(f"ERROR {test_id}")
            continue
        lines.append(f"{'PASSED' if ok else 'FAILED'} {test_id}")
    return "".join(line + "\n" for line in lines)


def parse_log(log: str) -> dict[str, str]:
    """Map every test id in a run_tests report to its status."""
    statuses = {}
    for line in log.splitlines():
        status, _, test_id = line.partition(" ")
        statuses[test_id] = status
    return statuses


def passed(log: str, test_id: str) -> bool:
    """True when the report says this exact test PASSED. A test missing from the report did not pass."""
    return parse_log(log).get(test_id) == "PASSED"


def _gate(log: str, test_ids: list[str]) -> list[bool]:
    statuses = parse_log(log)
    return [statuses.get(test_id) == "PASSED" for test_id in test_ids]


def run_task(task: Task, patch: Patch) -> TaskResult:
    """Grade one candidate patch.

    The repo's whole test suite runs on a copy of the task's pre-fix state and, once the patch
    is applied, runs again in full on a patched copy; the task's own state is never changed.
    The task is invalid when it has no FAIL_TO_PASS test, when a FAIL_TO_PASS test already
    passes before the patch, or when a PASS_TO_PASS test does not: its status is "invalid" and
    the patch is not applied. Otherwise the status is "resolved" when every FAIL_TO_PASS test
    and every PASS_TO_PASS test passes after the patch, and "unresolved" when one does not.
    A patch that raises makes the status "error".

    The pass counts are taken after the patch (0 when it was not applied). outcomes has one
    Outcome per FAIL_TO_PASS test and then per PASS_TO_PASS test, all "before" ones first, then
    the "after" ones when the patch was applied.
    """
    ids = task.fail_to_pass + task.pass_to_pass
    nf, np_ = len(task.fail_to_pass), len(task.pass_to_pass)
    before = _gate(run_tests(task.tests, copy.deepcopy(task.state)), ids)
    outcomes = [Outcome(test_id, "before", ok) for test_id, ok in zip(ids, before)]
    if not nf or any(before[:nf]) or not all(before[nf:]):
        return TaskResult(task.instance_id, "invalid", 0, nf, 0, np_, outcomes)
    try:
        patched = patch.apply(copy.deepcopy(task.state))
    except Exception:
        return TaskResult(task.instance_id, "error", 0, nf, 0, np_, outcomes)
    after = _gate(run_tests(task.tests, patched), ids)
    outcomes += [Outcome(test_id, "after", ok) for test_id, ok in zip(ids, after)]
    status = "resolved" if all(after) else "unresolved"
    return TaskResult(task.instance_id, status, sum(after[:nf]), nf, sum(after[nf:]), np_, outcomes)
