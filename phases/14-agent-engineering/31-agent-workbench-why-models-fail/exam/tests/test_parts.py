import asyncio
import copy
import csv
import json
import time

import pytest
from surfaces.catch import Failure, catch_matrix
from surfaces.harness import Finding, check_harness
from surfaces.monitor import Event, monitor
from surfaces.report import (
    SYMPTOMS,
    WORKBENCH_SURFACES,
    RepoTask,
    RunResult,
    compare,
    failure_report,
    stub_agent,
)
from surfaces.scorecard import COLUMNS, Audit, Scorecard
from surfaces.service import WorkbenchService

LOGIN = RepoTask(
    "add rate limiting to /login and a passing test",
    allowed_files=["api/login.py", "api/limits.py", "tests/test_login.py"],
    forbidden_files=["scripts/release.sh", ".env"],
    acceptance=["tests/test_login.py::test_login_is_rate_limited passes"],
)


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


def scores(**changes) -> dict:
    """Every surface healthy, apart from the changes."""
    base = dict.fromkeys(WORKBENCH_SURFACES, 2)
    base.update(changes)
    return base


@pytest.mark.skip("Part 1")
def test_failure_report(tmp_path) -> None:
    """The run comparison reports the lesson's failure modes for any task, and stays fast."""
    out = tmp_path / "failure_modes.json"
    reports = compare(LOGIN, out, hallucinated=["CHANGELOG.md", ".env", "README.md"])
    prompt_only = json.loads(out.read_text(encoding="utf-8"))
    assert prompt_only["missing_surfaces"] == WORKBENCH_SURFACES, (
        "missing surfaces keep the lesson's table order"
    )
    assert prompt_only["symptoms"] == SYMPTOMS, "every missing surface maps to its symptom"
    assert prompt_only["off_scope_writes"] == ["README.md", "CHANGELOG.md"], (
        "off-scope writes are the files the task neither allows nor forbids, once each, in write order"
    )
    assert prompt_only["forbidden_writes"] == ["scripts/release.sh", ".env"], (
        "forbidden writes are reported on their own, in write order"
    )
    assert prompt_only["unverified_success"] is True
    workbench = reports["workbench"]
    assert (workbench["off_scope_writes"], workbench["forbidden_writes"]) == ([], []), (
        "scope refuses the hallucinated writes"
    )
    assert workbench["actually_passing"] is True, "the full workbench passes"

    six = [s for s in WORKBENCH_SURFACES if s != "review"]
    assert stub_agent(LOGIN, six).label == "partial", "a run that lacks any surface is partial"
    assert prompt_only["label"] == "prompt-only", "a run with no surfaces is prompt-only"

    blind = failure_report(stub_agent(LOGIN, ["scope", "verification"]), LOGIN)
    assert (blind["actually_passing"], blind["unverified_success"]) == (False, True), (
        "verification fails closed without a captured test run"
    )
    unchecked = failure_report(stub_agent(LOGIN, ["scope", "feedback"]), LOGIN)
    assert unchecked["unverified_success"] is True, "a captured test run is not a verdict; the gate is"

    allowed = [f"src/mod_{i:05d}.py" for i in range(8000)]
    forbidden = [f"vendor/lib_{i:05d}.py" for i in range(8000)]
    touched: list[str] = []
    for i in range(8000):
        touched += [allowed[i], f"gen/out_{2 * i:05d}.py", f"gen/out_{2 * i + 1:05d}.py"]
        if i % 10 == 0:
            touched.append(forbidden[i // 10])
    codemod = RunResult("prompt-only", files_touched=touched)
    start = time.perf_counter()
    report = failure_report(codemod, RepoTask("split the monolith", allowed, forbidden, []))
    elapsed = time.perf_counter() - start
    assert report["off_scope_writes"] == [f"gen/out_{j:05d}.py" for j in range(16000)]
    assert report["forbidden_writes"] == forbidden[:800]
    assert elapsed < 0.05, "the report should be fast on large runs"


@pytest.mark.skip("Part 2")
def test_scorecard_roundtrip(tmp_path) -> None:
    """Audits survive the CSV exactly, a refused score stays refused, history is in time order."""
    path = tmp_path / "scorecard.csv"
    pacific = Audit(
        "acme/api",
        "2026-03-13T17:30:00-08:00",
        scores(state=1, scope=0, verification=None, review=1),
        'no test command; "make test" is a stub,\nso verification is refused',
    )
    web = Audit(
        "acme/web",
        "2026-03-14T09:00:00+01:00",
        {"handoff": 1, "review": 2, "verification": 2, "feedback": 2, "scope": 2, "state": 2, "instructions": 2},
    )
    london = Audit("acme/api", "2026-03-14T00:15:00+00:00", scores(verification=0), "AGENTS.md, 41 lines")

    card = Scorecard(str(path))
    card.record(pacific)
    card.record(web)
    before = path.read_bytes()
    Scorecard(str(path)).record(london)
    assert path.read_bytes().startswith(before), "audits are appended; earlier rows never change"

    reopened = Scorecard(str(path))
    history = reopened.history("acme/api")
    assert pacific in history and london in history, "an audit round-trips exactly, refused scores included"
    assert history == [london, pacific], "history is oldest first by the instant, whatever the UTC offset"
    assert reopened.history("acme/web") == [web], "each score lands in its own surface's column"
    assert reopened.history("acme/ios") == []

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == COLUMNS and len(rows) == 4, "one header row, then one row per audit"
    assert [row[COLUMNS.index("verification")] for row in rows[1:]] == ["", "2", "0"], (
        "a refused score is an empty field"
    )

    before = path.read_bytes()
    rejected = [
        Audit("acme/api", "2026-03-15T09:00:00", scores()),
        Audit("acme/api", "2026-03-15T09:00:00+00:00", {s: 2 for s in WORKBENCH_SURFACES if s != "handoff"}),
        Audit("acme/api", "2026-03-15T09:00:00+00:00", scores(observability=2)),
        Audit("acme/api", "2026-03-15T09:00:00+00:00", scores(review=3)),
        Audit("acme/api", "2026-03-15T09:00:00+00:00", scores(review=-1)),
    ]
    for audit in rejected:
        with pytest.raises(ValueError):
            reopened.record(audit)
    assert path.read_bytes() == before, "a rejected audit leaves the file as it was"

    empty = tmp_path / "same.csv"
    empty.touch()  # the file exists but holds nothing yet, as after a crash right after it was created
    same = Scorecard(str(empty))
    first = Audit("acme/api", "2026-03-14T00:15:00+00:00", scores())
    second = Audit("acme/api", "2026-03-13T16:15:00-08:00", scores(review=1))
    same.record(first)
    same.record(second)
    with open(empty, newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == COLUMNS, "an empty file gets the header row too"
    assert same.history("acme/api") == [first, second], (
        "audits at the same instant keep the order they were recorded in"
    )


FAILURES = [
    Failure("off-scope edit", ("verification", "review", "scope")),
    Failure("success on a 400", ("verification", "feedback")),
    Failure("restart from zero", ("handoff", "state")),
    Failure("self-approval", ("review",)),
    Failure("forbidden write", ("review", "instructions", "scope")),
    Failure("wrong acceptance criteria", ()),
    Failure("looks good reaches main", ("review", "verification")),
    Failure("lost goal", ("state",)),
]


@pytest.mark.skip("Part 3")
def test_catch_matrix(tmp_path) -> None:
    """Each failure stops at the first surface on the flow; add the surfaces that stop the most escapes."""
    write = [Failure("hallucinated write", ("review", "verification", "scope"))]
    assert catch_matrix(write, WORKBENCH_SURFACES).caught == {"hallucinated write": "scope"}, (
        "a failure stops at the first surface on the flow"
    )
    assert catch_matrix(write, ["review", "verification"]).caught == {"hallucinated write": "verification"}, (
        "a missing surface lets the failure on to the next one"
    )

    full = catch_matrix(FAILURES, WORKBENCH_SURFACES)
    assert full.caught["forbidden write"] == "scope", "the surfaces meet a failure in flowchart order"
    assert full.escaped == ["wrong acceptance criteria"], (
        "a failure no surface is built for escapes even the full workbench"
    )
    assert full.counts == {
        "scope": 2, "state": 2, "instructions": 0, "feedback": 1,
        "verification": 1, "review": 1, "handoff": 0,
    }, "each failure counts once, for the surface that stops it"
    assert full.next_surfaces == []

    partial = catch_matrix(FAILURES, ["instructions", "feedback", "handoff"])
    assert partial.caught == {
        "success on a 400": "feedback",
        "restart from zero": "handoff",
        "forbidden write": "instructions",
    }
    assert partial.escaped == [
        "off-scope edit", "self-approval", "wrong acceptance criteria", "looks good reaches main", "lost goal",
    ], "escaped failures are listed in input order"
    assert partial.next_surfaces == ["review", "state"], "the next surface stops the most failures that still escape"
    assert catch_matrix(FAILURES, []).next_surfaces == ["review", "state", "feedback"], (
        "a tie goes to the surface earlier on the flow"
    )
    assert catch_matrix(FAILURES, [], limit=2).next_surfaces == ["review", "state"], "at most limit surfaces"
    tie = [Failure("lost goal", ("state",)), Failure("guessed done", ("instructions",))]
    assert catch_matrix(tie, []).next_surfaces == ["state", "instructions"], (
        "a tie goes to the surface earlier on the flow"
    )
    for failures, present in (
        ([Failure("telemetry gap", ("observability",))], []),
        (FAILURES, ["Scope"]),
        ([Failure("lost goal", ()), Failure("lost goal", ("state",))], []),
    ):
        with pytest.raises(ValueError):
            catch_matrix(failures, present)

    card = Scorecard(str(tmp_path / "scorecard.csv"))
    card.record(Audit("acme/api", "2026-03-13T17:30:00-08:00", scores(state=1, scope=0, verification=None, review=1)))
    card.record(Audit("acme/api", "2026-03-14T00:15:00+00:00", scores(), "backfilled from the London run"))
    assert WorkbenchService(card).next_surfaces("acme/api", FAILURES) == ["review", "state"], (
        "the latest audit decides, and only healthy surfaces are present"
    )


LOG = [
    Event(1, "write", path="api/login.py"),
    Event(2, "run", exit_code=1),
    Event(3, "write", path="README.md"),
    Event(4, "claim"),
    Event(5, "write", path="README.md"),
    Event(6, "run", exit_code=0),
    Event(7, "claim"),
    Event(8, "run"),
    Event(9, "claim"),
    Event(10, "write", path="scripts/release.sh"),
    Event(11, "handoff"),
    Event(12, "end"),
]

VIOLATIONS = [
    {"seq": 3, "surface": "scope", "path": "README.md"},
    {"seq": 4, "surface": "feedback", "exit_code": 1},
    {"seq": 9, "surface": "feedback", "exit_code": None},
    {"seq": 10, "surface": "scope", "path": "scripts/release.sh"},
]


async def arriving(events):
    for event in events:
        yield event


def parsed(lines: list[str]) -> list[dict]:
    assert all(line.endswith("\n") and line.count("\n") == 1 for line in lines), "one JSON object per line"
    return [json.loads(line) for line in lines]


@pytest.mark.skip("Part 4")
def test_monitor_stream() -> None:
    """Violations come out of an at-least-once, out-of-order log as soon as they can be checked."""
    found = parsed(collect(monitor(arriving(LOG), LOGIN)))
    assert [v for v in found if v["surface"] == "scope"] == [VIOLATIONS[0], VIOLATIONS[3]], (
        "an off-scope path is reported once, at its first write"
    )
    assert [v for v in found if v["surface"] == "feedback"] == [VIOLATIONS[1], VIOLATIONS[2]], (
        "a claim is judged by the latest run before it, and a run without an exit code is no pass"
    )
    assert found == VIOLATIONS, "violations come out in seq order"

    by_seq = {event.seq: event for event in LOG}
    for order in ([1, 3, 2, 4, 6, 2, 5, 7, 9, 8, 4, 10, 12, 11, 3], list(range(12, 0, -1))):
        found = parsed(collect(monitor(arriving([by_seq[seq] for seq in order]), LOGIN)))
        assert found == VIOLATIONS, f"same violations whatever the arrival order, e.g. {order[:9]}"

    quiet = [Event(1, "claim"), Event(2, "run", exit_code=1), Event(3, "claim"), Event(4, "claim"), Event(5, "end")]
    assert parsed(collect(monitor(arriving(quiet), LOGIN))) == [
        {"seq": 1, "surface": "feedback", "exit_code": None},
        {"seq": 3, "surface": "feedback", "exit_code": 1},
        {"seq": 4, "surface": "feedback", "exit_code": 1},
        {"seq": 5, "surface": "handoff"},
    ], "every claim is judged on its own, and a session that ends without a handoff is reported at its end"

    with pytest.raises(ValueError, match=r"\b5\b\D*\b7\b"):
        collect(monitor(arriving([by_seq[seq] for seq in (1, 2, 3, 4, 6, 8, 9)]), LOGIN))

    pulled: list[int] = []

    async def probe():
        yield Event(2, "write", path="README.md")
        pulled.append(1)
        yield Event(1, "write", path="api/login.py")
        for seq in range(3, 300):
            pulled.append(seq)
            yield Event(seq, "run", exit_code=0)

    async def redelivered_end():
        yield Event(1, "end")
        for n in range(300):
            pulled.append(n)
            yield Event(1, "end")

    async def first_line(source) -> str:
        agen = monitor(source, LOGIN)
        line = await agen.__anext__()
        await agen.aclose()
        return line

    assert json.loads(asyncio.run(first_line(probe()))) == {"seq": 2, "surface": "scope", "path": "README.md"}
    assert len(pulled) <= 1, "a violation goes out as soon as its event can be checked"
    pulled.clear()
    assert json.loads(asyncio.run(first_line(redelivered_end()))) == {"seq": 1, "surface": "handoff"}
    assert not pulled, "a missing handoff goes out at the end event, not when the stream stops"


HARNESS = {
    "kind": "runtime",
    "children": {
        "agent_state": {"kind": "store", "durable": True},
        "chat": {"kind": "store", "durable": False},
        "feedback_log": {"kind": "store", "durable": True},
        "startup": {"kind": "trigger", "on": "agent_state", "to": "sandbox/builder/plan"},
        "next_turn": {"kind": "trigger", "on": "chat", "to": "sandbox/builder/act"},
        "on_feedback": {"kind": "trigger", "on": "feedback_log", "to": "sandbox/builder/act"},
        "task_close": {"kind": "trigger", "to": "review_inbox"},
        "review_inbox": {"kind": "queue", "to": "triage"},
        "triage": {"kind": "queue", "to": "reviewer/review"},
        "reviewer": {
            "kind": "worker",
            "policy": {"read": ["patch"], "write": ["review_report"]},
            "functions": {"review": {"to": ["review_report"]}},
        },
        "cron": {"kind": "trigger", "to": "sandbox/builder"},
        "retry": {"kind": "queue", "to": "retry_later"},
        "retry_later": {"kind": "queue", "to": "retry"},
        "on_failure": {"kind": "trigger", "to": "retry"},
        "lint_hook": {"kind": "trigger", "on": "sandbox/checkout", "to": "sandbox/linter/run"},
        "sandbox": {
            "kind": "runtime",
            "children": {
                "builder": {
                    "kind": "worker",
                    "policy": {"read": ["agent_state"], "write": ["patch"]},
                    "functions": {
                        "plan": {"to": ["sandbox/jobs"]},
                        "act": {"to": ["chat"]},
                        "handoff": {"to": ["agent_state"]},
                    },
                },
                "jobs": {"kind": "queue", "to": "sandbox/runner/pytest"},
                "runner": {"kind": "worker", "functions": {"pytest": {"to": ["feedback_log"]}}},
                "mcp": {
                    "kind": "runtime",
                    "children": {
                        "github": {
                            "kind": "worker",
                            "policy": {"capabilities": ["read_issue"]},
                            "functions": {"read_issue": {"to": []}},
                        },
                    },
                },
                "webhook": {"kind": "trigger", "to": "sandbox/mcp/github/read_issue"},
            },
        },
    },
}


@pytest.mark.skip("Part 5")
def test_harness_primitives() -> None:
    """Every trigger reaches a function, every worker has a policy, and the loop closes on durable state."""
    findings = check_harness(HARNESS)
    assert sorted(f for f in findings if f.code == "unresolved") == [
        Finding("lint_hook", "unresolved", "sandbox/checkout"),
        Finding("lint_hook", "unresolved", "sandbox/linter/run"),
        Finding("reviewer/review", "unresolved", "review_report"),
    ], "every ref (to, on, a function's to) is a full path, through nested runtimes"
    assert [f.path for f in findings if f.code == "no_policy"] == ["sandbox/runner"], (
        "every worker needs a policy, at any depth"
    )
    assert sorted(f.path for f in findings if f.code == "no_function") == ["cron", "lint_hook", "on_failure"], (
        "a trigger must reach a function, through any number of queues"
    )
    assert Finding("", "open_loop") in findings, "a loop through chat history does not close the workbench"
    assert findings == [
        Finding("", "open_loop"),
        Finding("cron", "no_function"),
        Finding("lint_hook", "no_function"),
        Finding("lint_hook", "unresolved", "sandbox/checkout"),
        Finding("lint_hook", "unresolved", "sandbox/linter/run"),
        Finding("on_failure", "no_function"),
        Finding("reviewer/review", "unresolved", "review_report"),
        Finding("sandbox/runner", "no_policy"),
    ], "findings are sorted by path, then code, then detail"

    closed = copy.deepcopy(HARNESS)
    closed["children"]["session_end"] = {"kind": "trigger", "to": "sandbox/builder/handoff"}
    closed["children"]["sandbox"]["children"]["builder"]["functions"]["plan"]["to"].append("session_end")
    assert check_harness(closed) == findings[1:], "the loop closes on the state file"

    with pytest.raises(ValueError):
        check_harness({"kind": "runtime", "children": {"cleanup": {"kind": "lambda"}}})
