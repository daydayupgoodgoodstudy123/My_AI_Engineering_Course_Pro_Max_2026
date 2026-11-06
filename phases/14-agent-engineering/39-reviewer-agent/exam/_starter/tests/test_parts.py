import asyncio
import csv
import hashlib
import io
import json
import time
from collections import Counter

import pytest
from reviewer.reconcile import Draft, Opinion, reconcile
from reviewer.reports import ReportConflict, ReportStore
from reviewer.rounds import build_review_rounds
from reviewer.rubric import RUBRIC, SCORERS, DimensionScore, ReviewerInputs, ReviewReport, SignOffQueue, review
from reviewer.threads import Comment, ThreadState, summarize_threads


def task(
    task_id: str = "T-001",
    goal: str = "add input validation to signup",
    touched: tuple = ("app/signup.py", "tests/test_signup.py"),
    active: str | None = None,
    next_action: str = "pick next task from board",
    feedback: list | None = None,
    gate: dict | None = None,
    approved: tuple = (),
) -> ReviewerInputs:
    """The lesson's clean change (T-001), with any artifact swapped out."""
    return ReviewerInputs(
        task_id=task_id,
        goal=goal,
        diff_summary={"touched": list(touched)},
        state={
            "active_task_id": active,
            "assumptions": ["users sign up with email + password only"],
            "next_action": next_action,
            "approved_scope": list(approved),
        },
        feedback=[{"command_id": "c1", "command": "pytest", "exit_code": 0}] if feedback is None else feedback,
        verdict={"passed": True, "findings": []} if gate is None else gate,
    )


def scores(report: ReviewReport) -> list[tuple[str, int]]:
    return [(d.name, d.score) for d in report.dimensions]


def score_of(report: ReviewReport, name: str) -> int:
    return next(d.score for d in report.dimensions if d.name == name)


def model_call(scorer, calls: Counter, latency: float = 0.002):
    """The scorer, taking as long as a model call would, and counted every time it runs."""

    def call(inputs: ReviewerInputs):
        calls[scorer.__name__] += 1
        time.sleep(latency)
        return scorer(inputs)

    return call


def refused(error: type[Exception], call, *args) -> bool:
    try:
        call(*args)
    except error:
        return True
    return False


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


@pytest.mark.skip("Part 1")
def test_rubric_review() -> None:
    """Every dimension scores what its docstring says, and the sign-off queue keeps each review."""
    clean = review(task())
    assert scores(clean) == [
        ("problem_fit", 1),
        ("scope_discipline", 2),
        ("assumptions", 2),
        ("verification_quality", 2),
        ("handoff_readiness", 2),
    ], "problem fit counts the distinct goal keywords found in touched paths"
    assert (clean.task_id, clean.total, clean.verdict) == ("T-001", 9, "pass")
    repeated = task(goal="reject signup requests when the signup email is blank", touched=["app/signup.py"])
    assert score_of(review(repeated), "problem_fit") == 1, "problem fit counts the distinct goal keywords found in touched paths"
    assert score_of(review(task(touched=["app/signup.py", "app/InputValidation.py"])), "problem_fit") == 2, (
        "touched paths are compared lowercased"
    )

    release_edit = {"passed": False, "findings": [{"code": "scope.forbidden", "severity": "block", "path": "scripts/release.sh"}]}
    forbidden = review(task(  # the builder also edited the release script, which the scope contract forbids
        touched=["app/signup.py", "app/validation.py", "scripts/release.sh"],
        gate=release_edit,
    ))
    assert (score_of(forbidden, "scope_discipline"), forbidden.total, forbidden.verdict) == (0, 8, "hard_fail"), (
        "a dimension at 0 is a hard fail, however high the total"
    )

    unverified = review(task(feedback=[]))
    assert (score_of(unverified, "verification_quality"), unverified.verdict) == (0, "hard_fail"), (
        "no feedback at all means nothing was verified"
    )
    mixed = task(feedback=[
        {"command_id": "c1", "command": "pytest", "exit_code": 1},
        {"command_id": "c2", "command": "pytest", "exit_code": 0},
    ])
    assert score_of(review(mixed), "verification_quality") == 1, "a failed command among passing ones scores 1"

    stalled = review(task(active="T-001", next_action=""))
    assert (score_of(stalled, "handoff_readiness"), stalled.verdict) == (0, "hard_fail"), (
        "an open task with no next_action cannot be handed off"
    )
    planned = review(task(active="T-001", next_action="finish the blank-email check"))
    assert score_of(planned, "handoff_readiness") == 1, "an open task with a next_action scores 1"

    grown = review(ReviewerInputs(  # the gate flagged docs/api.md, and the human grew the contract to cover it
        task_id="T-003",
        goal="add input validation to signup",
        diff_summary={"touched": ["app/signup.py", "docs/api.md"]},
        state={
            "active_task_id": "T-003",
            "assumptions": [],
            "next_action": "add the short-password check",
            "approved_scope": ["docs/api.md"],
        },
        feedback=[{"command_id": "c1", "command": "pytest", "exit_code": 0}],
        verdict={"passed": True, "findings": [{"code": "scope.off_scope", "severity": "warn", "path": "docs/api.md"}]},
    ))
    assert (grown.total, grown.verdict) == (7, "pass"), "an off-scope write a human approved is a contract grown deliberately"
    readme = review(task(
        touched=["app/signup.py", "docs/api.md", "README.md"],
        gate={"passed": True, "findings": [
            {"code": "scope.off_scope", "severity": "warn", "path": "docs/api.md"},
            {"code": "scope.off_scope", "severity": "warn", "path": "README.md"},
        ]},
        approved=["docs/api.md", "CHANGELOG.md"],
    ))
    assert score_of(readme, "scope_discipline") == 1, "an approval covers the path it names, not the other off-scope writes"
    approved_release = review(task(  # a human said yes to the release script, which the contract forbids
        touched=["app/signup.py", "app/validation.py", "scripts/release.sh"],
        gate=release_edit,
        approved=["scripts/release.sh"],
    ))
    assert (score_of(approved_release, "scope_discipline"), approved_release.verdict) == (0, "hard_fail"), (
        "no approval makes up for a forbidden write"
    )

    wrong_problem = review(ReviewerInputs(  # the lesson's T-002: tests pass, the wrong file changed
        task_id="T-002",
        goal="add input validation to signup",
        diff_summary={"touched": ["docs/api.md"]},
        state={"active_task_id": "T-002", "assumptions": [], "next_action": ""},
        feedback=[{"command": "pytest", "exit_code": 0}],
        verdict={"passed": True, "findings": [{"code": "scope.off_scope", "severity": "warn", "path": "docs/api.md"}]},
    ))
    assert scores(wrong_problem) == [
        ("problem_fit", 0),
        ("scope_discipline", 1),
        ("assumptions", 1),
        ("verification_quality", 2),
        ("handoff_readiness", 0),
    ]
    assert (wrong_problem.total, wrong_problem.verdict) == (4, "hard_fail")

    calls: Counter = Counter()
    queue = SignOffQueue([model_call(fn, calls) for fn in SCORERS])
    closed = [task(task_id=f"T-{7 * i % 20:03d}", feedback=[] if i % 4 == 3 else None) for i in range(20)]
    for inputs in closed:
        queue.submit(inputs)
    start = time.perf_counter()
    board = queue.board()
    opened = [queue.report(inputs.task_id) for inputs in closed]
    assert time.perf_counter() - start < 0.05, "reading the board and the reports must not review the tasks again"
    assert calls == {fn.__name__: 20 for fn in SCORERS}, "every scorer runs once per submitted task"
    assert board[2:4] == [("T-014", 9, "pass", []), ("T-001", 7, "hard_fail", ["verification_quality"])], (
        "the board lists tasks in the order they were first submitted"
    )
    assert opened == [review(inputs) for inputs in closed], "a kept report has every dimension in rubric order, with its note"

    later = task(task_id="T-100")
    kept = queue.submit(later)
    later.state.update(active_task_id="T-100", next_action="")  # the builder reopened the task afterwards
    assert queue.report("T-100") == kept, (
        "a kept report is a record of one review: later changes to the artifacts do not touch it"
    )
    assert queue.submit(later).verdict == "hard_fail", "a task submitted again is reviewed again"
    assert queue.report("T-100").verdict == "hard_fail", "the new report replaces the old one"
    queue.submit(closed[3])
    assert [row[0] for row in queue.board()] == [inputs.task_id for inputs in closed] + ["T-100"], (
        "the board has one row per task, in the order tasks were first submitted"
    )


NOTE = 'gate said "passed", but the diff only touches docs/api.md → the wrong half of the bug.\n\tCheck app/signup.py first.  '


def uniform(task_id: str, score, note: str = "ok", swap: str | None = None) -> ReviewReport:
    """A report that gives every rubric dimension 2, except `swap`, which gets `score`."""
    dims = [DimensionScore(name, score if name == swap else 2, note) for name in RUBRIC]
    return ReviewReport(task_id, sum(d.score for d in dims), "pass", dims)


@pytest.mark.skip("Part 2")
def test_report_history(tmp_path) -> None:
    """Each review is one attempt of its task; recorded attempts never change and read back exactly."""
    root = tmp_path / "reviews"
    first = ReviewReport("T-001", 8, "soft_fail", [  # a project rubric with a sixth dimension (lesson exercise 1)
        DimensionScore("problem_fit", 1, NOTE),
        DimensionScore("money_safety", 2, "refund paths untouched; amounts stay in integer cents"),
        DimensionScore("scope_discipline", 1, "off-scope warnings: 1"),
        DimensionScore("assumptions", 2, "1 assumptions recorded"),
        DimensionScore("verification_quality", 1, "mixed exit codes in feedback"),
        DimensionScore("handoff_readiness", 1, "active task not closed in state"),
    ])
    other = ReviewReport("T-002", 4, "hard_fail", [
        DimensionScore("problem_fit", 0, "goal keywords found in touched paths: none"),
        DimensionScore("scope_discipline", 1, "off-scope warnings: 1"),
        DimensionScore("assumptions", 1, "no assumptions recorded; either work was trivial or undocumented"),
        DimensionScore("verification_quality", 2, "all feedback exit zero"),
        DimensionScore("handoff_readiness", 0, "no next_action recorded"),
    ])
    fixed = uniform("T-001", 2, "all clear")
    rejected = uniform("T-001", 1, "still missing the password check", swap="problem_fit")

    store = ReportStore(root)
    digest = store.record(first, 1)
    blob = root / "objects" / f"{digest}.json"
    assert hashlib.sha256(blob.read_bytes()).hexdigest() == digest, "an object is named by the SHA-256 of its bytes"
    loaded = store.load("T-001", 1)
    assert loaded == first, "a report reads back exactly as it was recorded"
    assert [type(d.score) for d in loaded.dimensions] == [int] * 6, "scores read back as ints"
    assert store.record(first, 1) == digest, "recording an attempt again with the same report changes nothing"
    assert refused(ReportConflict, store.record, rejected, 1), "a recorded attempt never changes"
    assert refused(ValueError, store.record, rejected, 3), "a task's attempts are numbered 1, 2, 3, ... with no gaps"
    assert refused(ValueError, store.record, uniform("T-001", 2.0, swap="assumptions"), 2), "a score is an int from 0 to 2"
    assert refused(ValueError, store.record, uniform("T-001", True, swap="handoff_readiness"), 2), "a score is an int from 0 to 2"
    assert refused(ValueError, store.record, uniform("T-001", 3, swap="assumptions"), 2), "a score is an int from 0 to 2"

    assert store.record(first, 2) == digest, "a second review that found the same thing is attempt 2, with the same body"
    assert refused(ValueError, store.record, first, 0), "a task's attempts are numbered from 1"
    assert store.attempts("T-002") == []
    assert refused(ValueError, store.record, other, 2), "attempts are numbered per task"
    other_digest = store.record(other, 1)
    third = store.record(fixed, 3)
    index = [json.loads(line) for line in (root / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert index == [
        {"task": "T-001", "attempt": 1, "sha256": digest},
        {"task": "T-001", "attempt": 2, "sha256": digest},
        {"task": "T-002", "attempt": 1, "sha256": other_digest},
        {"task": "T-001", "attempt": 3, "sha256": third},
    ], "the index gets one line per recorded attempt, in the order they were recorded"
    assert sorted(p.name for p in (root / "objects").iterdir()) == sorted(f"{d}.json" for d in {digest, other_digest, third}), (
        "equal reports share one object, and a rejected record writes nothing"
    )

    reopened = ReportStore(root)
    assert reopened.attempts("T-001") == [1, 2, 3], "a store opened again sees every recorded attempt"
    assert [reopened.load("T-001", n) for n in (1, 2, 3)] == [first, first, fixed], "each attempt reads back its own report"
    assert reopened.load("T-002", 1) == other
    reopened.record(other, 2)
    assert reopened.attempts("T-002") == [1, 2], "a store opened again goes on numbering where it left off"
    with pytest.raises(KeyError):
        reopened.load("T-001", 4)
    assert refused(KeyError, reopened.load, "T-001", 0), "unknown attempts raise KeyError, attempt 0 included"


SIGNUP = ReviewerInputs(
    task_id="T-007",
    goal="add input validation to signup",
    diff_summary={"touched": ["app/signup.py", "tests/test_signup.py", "docs/api.md"]},
    state={
        "active_task_id": None,
        "assumptions": ["users sign up with email + password only"],
        "next_action": "pick next task from board",
    },
    feedback=[
        {"command_id": "3f2a9c1d0b7e", "command": "pytest -q", "exit_code": 1},
        {"command_id": "8c41d0e7a2f5", "command": "pytest -q", "exit_code": 0},
    ],
    verdict={"passed": True, "findings": [{"code": "scope.off_scope", "severity": "warn", "path": "docs/api.md"}]},
)


def draft(reviewer: str, *rows) -> Draft:
    """rows are (dimension, score, citation, ...)."""
    return Draft(reviewer, [Opinion(dim, score, f"{dim} {score}", tuple(cites)) for dim, score, *cites in rows])


AGREED = (
    ("problem_fit", 2, "file:app/signup.py", "file:tests/test_signup.py"),
    ("scope_discipline", 2, "finding:scope.off_scope"),
    ("assumptions", 2, "state:assumptions"),
    ("verification_quality", 2, "feedback:8c41d0e7a2f5"),
    ("handoff_readiness", 2, "state:next_action"),
)


@pytest.mark.skip("Part 3")
def test_reconcile_reviewers() -> None:
    """Scores count only with evidence behind them, and two reviewers' drafts become one report."""
    a = draft(
        "judge-a",
        ("problem_fit", 2, "file:app/signup.py"),
        ("scope_discipline", 1, "finding:scope.off_scope"),
        ("assumptions", 2, "state:assumptions"),
        ("verification_quality", 2, "feedback:8c41d0e7a2f5"),
        ("handoff_readiness", 2, "state:active_task_id"),
    )
    b = draft(
        "judge-b",
        ("verification_quality", 1, "feedback:3f2a9c1d0b7e"),
        ("handoff_readiness", 2, "state:next_action"),
        ("problem_fit", 2, "file:App/signup.py"),
        ("assumptions", 2, "state:assumptions"),
        ("scope_discipline", 1, "finding:scope.off_scope"),
    )
    result = reconcile(SIGNUP, a, b)
    assert [d.note for d in result.report.dimensions] == [
        "judge-a: problem_fit 2 | judge-b: problem_fit 2",
        "judge-a: scope_discipline 1 | judge-b: scope_discipline 1",
        "judge-a: assumptions 2 | judge-b: assumptions 2",
        "judge-a: verification_quality 2 | judge-b: verification_quality 1",
        "judge-a: handoff_readiness 2 | judge-b: handoff_readiness 2",
    ], "each dimension pairs the two reviewers' opinions on it, in rubric order"
    assert result.unsupported == [("judge-b", "problem_fit")], (
        "a citation must name something in the artifacts, exactly: paths are case-sensitive"
    )
    assert scores(result.report) == [
        ("problem_fit", 1),
        ("scope_discipline", 1),
        ("assumptions", 2),
        ("verification_quality", 1),
        ("handoff_readiness", 2),
    ], "a dimension scores the mean of the two counted scores, rounded down"
    assert (result.report.task_id, result.report.total, result.report.verdict) == ("T-007", 7, "pass"), (
        "a total of exactly 7 passes"
    )
    assert result.escalate == [], "a difference of 1 is not an escalation"

    a = draft(
        "judge-a",
        ("handoff_readiness", 1, "state:next_action"),
        ("assumptions", 2),
        ("verification_quality", 1, "feedback:3f2a9c1d0b7e"),
        ("problem_fit", 2, "file:app/signup.py", "file:app/forms.py"),
        ("scope_discipline", 1, "finding:scope.off_scope"),
    )
    b = draft(
        "judge-b",
        ("problem_fit", 2, "file:tests/test_signup.py"),
        ("scope_discipline", 1, "finding:scope.forbidden"),
        ("assumptions", 2, "state:assumptions"),
        ("verification_quality", 1, "feedback:pytest -q"),
        ("handoff_readiness", 1),
    )
    result = reconcile(SIGNUP, a, b)
    assert result.unsupported == [
        ("judge-a", "problem_fit"),
        ("judge-a", "assumptions"),
        ("judge-b", "scope_discipline"),
        ("judge-b", "verification_quality"),
        ("judge-b", "handoff_readiness"),
    ], (
        "an opinion is supported only when it cites something and every citation is in the artifacts"
    )
    assert scores(result.report) == [(name, 1) for name in RUBRIC], "an unsupported score counts as at most 1"
    assert (result.report.total, result.report.verdict) == (5, "soft_fail"), "a total of exactly 5 is a soft fail"

    split = draft("judge-b", ("problem_fit", 0), *AGREED[1:])
    result = reconcile(SIGNUP, draft("judge-a", *AGREED), split)
    assert result.escalate == ["problem_fit"], "a dimension escalates when the two counted scores differ by more than 1"
    assert scores(result.report)[0] == ("problem_fit", 1), "an escalated dimension still scores the mean, rounded down"
    assert (result.report.total, result.report.verdict) == (9, "pass"), "escalation does not change the verdict"
    assert result.unsupported == [("judge-b", "problem_fit")]

    a = draft("judge-a", *AGREED[:4], ("handoff_readiness", 2, "state:handoff"))
    b = draft(
        "judge-b",
        *AGREED[:1],
        ("scope_discipline", 1, "finding:scope.off_scope"),
        *AGREED[2:4],
        ("handoff_readiness", 0, "state:next_action"),
    )
    result = reconcile(SIGNUP, a, b)
    assert result.unsupported == [("judge-a", "handoff_readiness")]
    assert result.escalate == [], "escalation compares the counted scores, after the evidence cap"
    assert (result.report.total, result.report.verdict) == (7, "hard_fail"), (
        "any dimension at 0 is a hard fail, whatever the total"
    )

    full = draft("judge-a", *AGREED)
    assert refused(ValueError, reconcile, SIGNUP, full, draft("judge-b", *AGREED[:4])), (
        "each reviewer scores every rubric dimension exactly once"
    )
    extra = draft("judge-b", *AGREED, ("money_safety", 2, "state:next_action"))
    assert refused(ValueError, reconcile, SIGNUP, full, extra), (
        "each reviewer scores every rubric dimension exactly once"
    )
    assert refused(ValueError, reconcile, SIGNUP, draft("judge-a", *AGREED, AGREED[0]), full), (
        "each reviewer scores every rubric dimension exactly once"
    )
    assert refused(ValueError, reconcile, SIGNUP, draft("judge-a", *AGREED[:4], AGREED[0]), full), (
        "each reviewer scores every rubric dimension exactly once"
    )


V0 = "def signup(email, password):\n    return create_user(email, password)\n"
V1 = (
    "def signup(email, password):\n"
    "    if not email:\n"
    "        raise ValueError('email is required')\n"
    "    return create_user(email, password)\n"
)
V1_FORMATTED = V1.replace("'", '"')
T1 = "def test_blank_email():\n    ...\n"
T2 = T1 + "\n\ndef test_short_password():\n    ...\n"


def round_report(points: list[int], verdict: str) -> ReviewReport:
    return ReviewReport("T-001", sum(points), verdict, [DimensionScore(n, s, "") for n, s in zip(RUBRIC, points)])


@pytest.mark.skip("Part 4")
def test_build_review_rounds() -> None:
    """Builder and reviewer take turns; the reviewer reads a frozen snapshot, and every round streams as it ends."""
    workspace = {"README.md": "# signup service\n", "docs/notes.md": "scratch\n", "app/signup.py": V0}
    reports = {
        1: round_report([1, 1, 1, 2, 1], "soft_fail"),
        2: round_report([1, 1, 1, 1, 1], "soft_fail"),
        3: round_report([2, 2, 1, 2, 1], "pass"),
    }
    received: list[str] = []
    started: list[int] = []
    handed: list = []
    seen: list[dict] = []
    refused_writes: list[int] = []
    hooks: list = []

    async def formatter(ws: dict) -> None:
        await asyncio.sleep(0.005)
        ws["app/signup.py"] = V1_FORMATTED

    async def builder(n: int, ws: dict, last) -> None:
        started.append(sum(1 for line in received if not line.startswith("round,")))
        handed.append(last)
        if n == 1:
            ws["app/signup.py"] = V1
            await asyncio.sleep(0)
            ws["tests/test_signup.py"] = T1
            hooks.append(asyncio.create_task(formatter(ws)))  # a format-on-save hook, still running when the turn returns
        elif n == 2:
            del ws["docs/notes.md"]
            ws["README.md"] = "# signup service\n"
        else:
            ws["tests/test_signup.py"] = T2

    async def reviewer(n: int, snapshot) -> ReviewReport:
        await asyncio.sleep(0.02)  # the model call
        seen.append(dict(snapshot))
        try:
            snapshot["app/signup.py"] = "patched by the reviewer"
        except TypeError:
            refused_writes.append(n)
        return reports[n]

    async def run(rounds) -> None:
        async for line in rounds:
            received.append(line)
        await asyncio.gather(*hooks)

    asyncio.run(run(build_review_rounds(workspace, builder, reviewer, max_rounds=3)))
    readme = "# signup service\n"
    assert seen == [
        {"app/signup.py": V1, "README.md": readme, "docs/notes.md": "scratch\n", "tests/test_signup.py": T1},
        {"app/signup.py": V1_FORMATTED, "README.md": readme, "tests/test_signup.py": T1},
        {"app/signup.py": V1_FORMATTED, "README.md": readme, "tests/test_signup.py": T2},
    ], "the reviewer reads the workspace as it was when the builder's turn returned"
    assert refused_writes == [1, 2, 3], "the reviewer cannot write to the snapshot"
    assert workspace["app/signup.py"] == V1_FORMATTED
    records = [record for line in received for record in csv.reader([line])]
    assert list(csv.reader(io.StringIO("".join(received), newline=""))) == records, "every record ends with a line break"
    assert records == [
        ["round", "changed", "total", "verdict", "next"],
        ["1", "app/signup.py;tests/test_signup.py", "6", "soft_fail", "build"],
        ["2", "app/signup.py;docs/notes.md", "5", "soft_fail", "build"],
        ["3", "tests/test_signup.py", "8", "pass", "done"],
    ], "one CSV record per round: round, changed, total, verdict, next"
    assert started == [0, 1, 2], "each round's record goes out before the next builder turn starts"
    assert handed == [None, reports[1], reports[2]], "the next builder turn gets the latest report"

    def every_round_says(points: list[int], verdict: str, max_rounds: int) -> tuple[list[list[str]], list[int]]:
        """Run the loop with a builder that always writes V1 and a reviewer that always says the same."""
        turns: list[int] = []

        async def same_edit(n: int, ws: dict, last) -> None:
            turns.append(n)
            ws["app/signup.py"] = V1

        async def same_report(n: int, snapshot) -> ReviewReport:
            return round_report(points, verdict)

        lines = collect(build_review_rounds({"app/signup.py": V0}, same_edit, same_report, max_rounds=max_rounds))
        return [next(csv.reader([line])) for line in lines[1:]], turns

    assert every_round_says([2, 2, 2, 2, 1], "pass", 3) == ([["1", "app/signup.py", "9", "pass", "done"]], [1]), (
        "a pass ends the loop"
    )
    assert every_round_says([0, 1, 1, 1, 1], "hard_fail", 3) == ([["1", "app/signup.py", "4", "hard_fail", "human"]], [1]), (
        "a hard fail halts the loop for a human"
    )
    assert every_round_says([1, 1, 1, 2, 1], "soft_fail", 2) == (
        [["1", "app/signup.py", "6", "soft_fail", "build"], ["2", "", "6", "soft_fail", "human"]],
        [1, 2],
    ), "when the last round does not pass, a human takes over"

    async def tests_only(n: int, ws: dict, last) -> None:
        if n == 1:
            ws["tests/test_signup.py"] = T1
            hooks.append(asyncio.create_task(formatter(ws)))  # reformats app/signup.py, which this turn did not touch

    async def slow_reviewer(n: int, snapshot) -> ReviewReport:
        await asyncio.sleep(0.02)
        return reports[n]

    late = collect(build_review_rounds({"app/signup.py": V1}, tests_only, slow_reviewer, max_rounds=2))
    assert [next(csv.reader([line]))[1] for line in late[1:]] == ["tests/test_signup.py", "app/signup.py"], (
        "a write that lands during the review is a change of the next round"
    )


COMMENTS = [
    Comment("c9", "c8", "reviewer", 33, "checked app/signup.py, agreed", resolve=True),
    Comment("c3", "c2", "builder", 40, "tests/test_signup.py::test_blank_email"),
    Comment("assume-a", None, "reviewer", 15, "is email + password the only signup path?", dimension="assumptions"),
    Comment("c11", "c10", "builder", 34, "closing this", resolve=True),
    Comment("c11a", "c11", "reviewer", 44, "only the reviewer closes a thread"),
    Comment("scope-a", None, "reviewer", 11, "docs/api.md is outside the contract", dimension="scope_discipline"),
    Comment("c6", "c5", "builder", 31, "also renamed a section in docs/api.md"),
    Comment("c1", "fit-a", "builder", 20, "moved the check into app/signup.py"),
    Comment("fit-b", None, "reviewer", 13, "a blank email still reaches create_user", dimension="problem_fit"),
    Comment("c4", "c3", "reviewer", 50, "confirmed", resolve=True),
    Comment("handoff-a", None, "reviewer", 14, "next_action is empty", dimension="handoff_readiness"),
    Comment("c5", "scope-a", "reviewer", 21, "fine, the contract allows doc changes", resolve=True),
    Comment("c5a", "scope-a", "builder", 16, "the contract now lists docs/api.md", resolve=True),
    Comment("c2", "c1", "reviewer", 30, "where is the test for it?"),
    Comment("verify-a", None, "reviewer", 12, "the first pytest run failed; which run proves it?", dimension="verification_quality"),
    Comment("c8", "fit-b", "builder", 23, "fixed", resolve=True),
    Comment("fit-a", None, "reviewer", 10, "the change only touches docs/api.md", dimension="problem_fit"),
    Comment("c7", "verify-a", "builder", 25, "re-ran it, green now", resolve=True),
    Comment("c10", "handoff-a", "reviewer", 24, "next_action is set now", resolve=True),
]


@pytest.mark.skip("Part 5")
def test_comment_threads() -> None:
    """Replies nest under their finding, only the reviewer resolves, and a later reply reopens."""
    summary = summarize_threads(COMMENTS)
    assert [t.finding for t in summary.threads] == ["fit-a", "scope-a", "verify-a", "fit-b", "handoff-a", "assume-a"], (
        "threads are listed by the time of their finding"
    )
    assert [(t.comments, t.last_at) for t in summary.threads] == [(5, 50), (4, 31), (2, 25), (3, 33), (4, 44), (1, 15)], (
        "a reply at any depth belongs to its finding's thread"
    )
    assert [t.status for t in summary.threads] == ["resolved", "open", "open", "resolved", "open", "open"], (
        "only the reviewer resolves a thread, and anything posted after the resolve reopens it"
    )
    assert summary.self_resolved == ["verify-a", "handoff-a"], "threads the builder marked resolved are reported, and stay open"
    assert list(summary.open_by_dimension.items()) == [
        ("problem_fit", 0),
        ("scope_discipline", 1),
        ("assumptions", 1),
        ("verification_quality", 1),
        ("handoff_readiness", 1),
    ], "open threads are counted for every rubric dimension, in rubric order"
    assert summary.threads[0] == ThreadState("fit-a", "problem_fit", "resolved", 5, 50)

    reworked = summarize_threads([
        Comment("c24", "c23", "reviewer", 39, "green on the new commit", resolve=True),
        Comment("assume-b", None, "reviewer", 30, "where is the email-only assumption written down?", dimension="assumptions"),
        Comment("c20", "assume-b", "reviewer", 31, "found it in the state file", resolve=True),
        Comment("c21", "c20", "reviewer", 32, "but the docs still say otherwise"),
        Comment("verify-b", None, "reviewer", 33, "which run proves the fix?", dimension="verification_quality"),
        Comment("c23", "c22", "builder", 37, "that run was on the old commit, re-ran it"),
        Comment("c22", "verify-b", "reviewer", 35, "the second run", resolve=True),
    ])
    assert [t.status for t in reworked.threads] == ["open", "resolved"], (
        "a later reply reopens the thread, the reviewer's own too, and the reviewer's latest resolve closes it again"
    )

    with pytest.raises(ValueError, match="style-a"):
        summarize_threads(COMMENTS + [Comment("style-a", None, "reviewer", 16, "use f-strings", dimension="style")])
    with pytest.raises(ValueError, match="c12"):
        summarize_threads(COMMENTS + [Comment("c12", "c404", "builder", 41, "answering a deleted comment")])
