import copy
import dataclasses
import json
import re
import shlex
import time

import pytest
from handoffpkt.chain import BranchHead, BrokenChain, branch_heads
from handoffpkt.cleanup import RepoSnapshot, clean_state
from handoffpkt.history import HandoffHistory
from handoffpkt.packet import (
    DirtyWorkbench,
    HandoffPayload,
    NoNextAction,
    PacketTooLarge,
    WorkbenchSnapshot,
    generate_handoff,
    packet_json,
    render_markdown,
    trim_feedback,
)
from handoffpkt.stream import trim_stream


def record(n: int, command, exit_code, error=None) -> dict:
    """One feedback record, shaped like lesson 37's feedback_record.jsonl."""
    return {"command_id": f"c{n:03d}", "command": command, "exit_code": exit_code, "duration_ms": 120 * n, "error": error}


SESSION_LOG = [
    record(1, ["pytest", "-q"], 0),
    record(2, ["ruff", "check", "."], 0),
    record(3, ["pytest", "tests/test_signup.py", "-x"], 1),
    record(4, ["pytest", "tests/test_signup.py::test_burst"], None, "timeout after 30.0s"),
    record(5, ["sed", "-n", "1,80p", "app/limits/window.py"], 0),
    record(6, ["python", "-c", "import app.limits; print(app.limits.WINDOW)"], 0),
    record(7, ["pytest", "tests/test_signup.py", "-x"], -9),
    record(8, ["git", "commit", "-m", "limit: 5 per minute"], 0),
    record(9, ["pytest", "tests/test_signup.py", "-x"], 0),
    record(10, ["ruff", "check", "."], 0),
    record(11, ["pytest", "tests/test_signup.py::test_burst", "--timeout", "60"], 1),
    record(12, ["pytest", "-q"], 0),
]
COMMAND_LINES = [
    "pytest -q",
    "ruff check .",
    "pytest tests/test_signup.py -x",
    "pytest tests/test_signup.py::test_burst",
    "sed -n 1,80p app/limits/window.py",
    "python -c 'import app.limits; print(app.limits.WINDOW)'",
    "pytest tests/test_signup.py -x",
    "git commit -m 'limit: 5 per minute'",
    "pytest tests/test_signup.py -x",
    "ruff check .",
    "pytest tests/test_signup.py::test_burst --timeout 60",
    "pytest -q",
]
STATE = {
    "active_task_id": "T-014",
    "branch": "feat/signup-rate-limit",
    "last_known_good_commit": "4be1c0d",
    "blockers": ["awaiting a decision on the rate-limit window"],
    "next_action": "Rerun pytest tests/test_signup.py::test_burst --timeout 60,\n"
    "    then fix the window math in app/limits/window.py",
}
VERDICT = {
    "passed": False,
    "findings": [
        {"code": "feedback.null_exit", "severity": "block", "detail": "missing exit for pytest tests/test_signup.py::test_burst"},
        {"code": "scope.off_scope", "severity": "warn", "detail": "off-scope writes: ['README.md']"},
        {"code": "lint.clean", "severity": "info", "detail": "ruff found nothing to fix"},
        {"code": "coverage.minor_regression", "severity": "warn", "detail": "coverage dropped 1.00%"},
    ],
}
TOUCHED = ["app/signup.py", "tests/test_signup.py", "app/limits/window.py", "app/signup.py", "README.md"]


def session_snapshot(**changes) -> WorkbenchSnapshot:
    """The end of one session on T-014. No reviewer ran, so there is no review report."""
    snapshot = WorkbenchSnapshot(
        task_id="T-014",
        state=copy.deepcopy(STATE),
        verdict=copy.deepcopy(VERDICT),
        review=None,
        feedback=copy.deepcopy(SESSION_LOG),
        diff_summary={"touched": list(TOUCHED)},
    )
    return dataclasses.replace(snapshot, **changes)


def long_session(n: int = 3500) -> list[dict]:
    """A long session: the agent reads files, greps and reruns tests, over and over."""
    log = []
    for i in range(n):
        command = [
            ["pytest", "-q", f"tests/test_window.py::test_slot[{i}]"],
            ["sed", "-n", f"{i},{i + 40}p", "app/limits/window.py"],
            ["grep", "-rn", "rate_window", f"docs/limits_{i % 9}.md"],
            ["ruff", "check", "app/limits"],
        ][i % 4]
        log.append(record(i + 1, command, 0))
    log[100]["exit_code"] = 1
    log[700].update(exit_code=None, error="timeout after 30.0s")
    return log


def sections(markdown: str) -> dict[str, list[str]]:
    """The non-blank lines under each '## ' heading of handoff.md."""
    found: dict[str, list[str]] = {}
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            lines = found.setdefault(line[3:], [])
        elif line.strip():
            lines.append(line)
    return found


def code(line: str) -> str:
    """The text of a '- `...`' line."""
    assert line.startswith("- `") and line.endswith("`"), line
    return line[3:-1]


def size(payload: HandoffPayload) -> int:
    return len(packet_json(payload).encode("utf-8"))


@pytest.mark.skip("Part 1")
def test_generate_handoff() -> None:
    """The packet carries the seven fields from the artifacts, and handoff.md is a render of handoff.json."""
    markdown, payload = generate_handoff(session_snapshot())
    assert payload.open_risks == [
        {"severity": "block", "detail": "missing exit for pytest tests/test_signup.py::test_burst"},
        {"severity": "warn", "detail": "off-scope writes: ['README.md']"},
        {"severity": "warn", "detail": "coverage dropped 1.00%"},
        {"severity": "warn", "detail": "open blocker: awaiting a decision on the rate-limit window"},
        {"severity": "warn", "detail": "review report missing"},
    ], "open_risks: block and warn findings, the blockers, then the review; a missing review report is a risk"
    for review, expected in (
        ({"verdict": "soft_fail", "total": "n/a"}, [{"severity": "warn", "detail": "review total 'n/a' is not a number"}]),
        ({"verdict": "soft_fail", "total": 5}, [{"severity": "warn", "detail": "review total 5 below 7"}]),
        ({"verdict": "pass", "total": 7}, []),
    ):
        risks = generate_handoff(session_snapshot(review=review))[1].open_risks
        assert risks[4:] == expected, "a review total that is not a number is a risk; a total of 7 or more is not"

    assert (payload.commands_run, payload.commands_omitted) == (COMMAND_LINES, 0), "every command as one shell line"
    assert payload.failed_attempts == [
        "pytest tests/test_signup.py -x -> exit 1",
        "pytest tests/test_signup.py::test_burst -> no exit code (timeout after 30.0s)",
        "pytest tests/test_signup.py -x -> exit -9",
        "pytest tests/test_signup.py::test_burst --timeout 60 -> exit 1",
    ], "a command that never exited is a failed attempt too"
    assert payload.summary == "T-014: 12 commands run, 4 failed; 4 files changed; gate failed; review missing."
    assert payload.feedback_tail == [SESSION_LOG[i] for i in (2, 3, 6, 7, 8, 9, 10, 11)], (
        "the last 5 records plus every earlier failure, in log order"
    )
    ok, lint, red = (
        {"command": "pytest", "exit_code": 0},
        {"command": "ruff check .", "exit_code": 0},
        {"command": "pytest test_signup.py", "exit_code": 1},
    )
    demo = [dict(ok), dict(lint), dict(red), dict(ok), dict(lint), dict(red), dict(ok)]
    assert trim_feedback(demo, k=2) == [red, red, ok], "each record once, where it is in the log, even when two are equal"
    assert trim_feedback(demo, k=0) == [red, red], "k=0 keeps the failures only"
    assert trim_feedback(demo[:4]) == demo[:4], "a log shorter than k is kept whole, as in the lesson's demo"
    assert demo == [ok, lint, red, ok, lint, red, ok]

    assert payload.changed_files == ["README.md", "app/limits/window.py", "app/signup.py", "tests/test_signup.py"], (
        "every touched path once, sorted"
    )
    codemod = [f"app/{name}/{part}.py" for name in ("signup", "limits", "auth") for part in "zyxwvutsrqponm"]
    touched = generate_handoff(session_snapshot(diff_summary={"touched": codemod + codemod[::3]}))[1].changed_files
    assert touched == sorted(codemod), "every touched path once, sorted, so the same artifacts give the same packet"
    assert (payload.task_id, payload.branch, payload.last_known_good_commit) == ("T-014", "feat/signup-rate-limit", "4be1c0d")
    assert payload.next_action == (
        "Rerun pytest tests/test_signup.py::test_burst --timeout 60, then fix the window math in app/limits/window.py"
    ), "next_action on one line"
    assert payload.verdict_pointer == {"verdict": "outputs/verification/T-014.json", "review": "outputs/review/T-014.json"}
    no_action = {key: value for key, value in STATE.items() if key != "next_action"}
    for state in (no_action, {**no_action, "next_action": " \n\t "}):
        with pytest.raises(NoNextAction):
            generate_handoff(session_snapshot(state=state))

    md = sections(markdown)
    assert md["Next action"] == [payload.next_action], "handoff.md is a render of the payload: the same next action"
    assert [code(line) for line in md["Changed files"]] == payload.changed_files
    assert [code(line) for line in md["Commands run"]] == payload.commands_run
    assert md["Failed attempts"] == [f"- {attempt}" for attempt in payload.failed_attempts]
    assert md["Open risks"] == [f"- [{risk['severity']}] {risk['detail']}" for risk in payload.open_risks]
    assert render_markdown(HandoffPayload(**json.loads(packet_json(payload)))) == markdown, (
        "handoff.md can be rendered again from handoff.json alone"
    )

    log = long_session()
    lines = [shlex.join(entry["command"]) for entry in log]
    long = session_snapshot(feedback=log, review={"verdict": "pass", "total": 8})
    budget = 12_000
    start = time.perf_counter()
    markdown, payload = generate_handoff(long, max_bytes=budget)
    elapsed = time.perf_counter() - start
    kept = len(payload.commands_run)
    assert size(payload) <= budget, "handoff.json fits in max_bytes"
    assert 0 < kept < len(log) and payload.commands_run == lines[-kept:], "the most recent commands stay, oldest first"
    assert payload.commands_omitted == len(log) - kept, "commands_omitted counts the commands left out"
    assert payload.failed_attempts == [
        "pytest -q 'tests/test_window.py::test_slot[100]' -> exit 1",
        "pytest -q 'tests/test_window.py::test_slot[700]' -> no exit code (timeout after 30.0s)",
    ] and payload.feedback_tail == [log[100], log[700], *log[-5:]], "failures are never dropped to make room"
    one_more = dataclasses.replace(payload, commands_run=lines[-kept - 1 :], commands_omitted=payload.commands_omitted - 1)
    assert size(one_more) > budget, "keep every recent command that fits"
    assert sections(markdown)["Commands run"] == [f"- `{line}`" for line in payload.commands_run] + [
        f"- ... and {payload.commands_omitted} earlier commands, in the full feedback log"
    ], "handoff.md lists the commands handoff.json kept, and how many it left out"
    assert elapsed < 0.1, "fitting a long session into max_bytes should be fast"
    floor = size(dataclasses.replace(payload, commands_run=[], commands_omitted=len(log)))
    assert generate_handoff(long, max_bytes=floor)[1].commands_run == [], "at the floor every command is left out"
    with pytest.raises(PacketTooLarge):
        generate_handoff(long, max_bytes=floor - 1)


PACKET = {
    "task_id": "T-014",
    "branch": "feat/signup-rate-limit",
    "last_known_good_commit": "4be1c0d",
    "summary": "T-014: Rate-Limit für /signup — 12 commands run, 4 failed; review missing.",
    "changed_files": ["README.md", "app/limits/window.py", "app/signup.py"],
    "commands_run": ["pytest -q", "git commit -m 'limit: 5 per minute'"],
    "commands_omitted": 0,
    "failed_attempts": ["pytest tests/test_signup.py::test_burst -> no exit code (timeout after 30.0s)"],
    "open_risks": [
        {"severity": "block", "detail": "missing exit for pytest tests/test_signup.py::test_burst"},
        {"severity": "warn", "detail": "open blocker: awaiting a decision on the rate-limit window"},
    ],
    "next_action": "Rerun pytest tests/test_signup.py::test_burst --timeout 60",
    "verdict_pointer": {"verdict": "outputs/verification/T-014.json", "review": "outputs/review/T-014.json"},
    "feedback_tail": [
        {"command_id": "c004", "command": ["pytest", "tests/test_signup.py::test_burst"], "exit_code": None,
         "duration_ms": 30000, "error": "timeout after 30.0s"},
        {"command_id": "c012", "command": ["pytest", "-q"], "exit_code": 0, "duration_ms": 0, "error": None,
         "started_at": 1793000086.1},
    ],
}


@pytest.mark.skip("Part 2")
def test_history_roundtrip(tmp_path) -> None:
    """Each session's packet is kept exactly, numbered from the files on disk, and points to the one before."""
    root = tmp_path / "outputs" / "handoff" / "T-014"
    history = HandoffHistory(root)
    assert (history.sessions(), history.latest()) == ([], None), "a task with no handoff yet"
    assert history.save(PACKET) == 1
    assert history.load(1) == {**PACKET, "session": 1, "previous": None}, "the first session has no previous"
    assert history.save(copy.deepcopy(PACKET)) == 1, "the same packet saved again is the same session"
    (root / "session-0001.md").write_text("# Handoff: T-014\n", encoding="utf-8")
    (root / "notes.txt").write_text("ask about the window before Friday\n", encoding="utf-8")
    (root / "session-0001.json~").write_text(json.dumps(PACKET), encoding="utf-8")

    reopened = HandoffHistory(root)
    for n in range(2, 13):
        assert reopened.save(dict(PACKET, next_action=f"step {n}")) == n, "the next number comes from the session files"
    assert reopened.sessions() == list(range(1, 13)), "sessions in number order"
    latest = HandoffHistory(root).latest()
    assert latest is not None and (latest["session"], latest["previous"], latest["next_action"]) == (12, 11, "step 12"), (
        "latest is the highest session number on disk"
    )
    assert reopened.load(1) == {**PACKET, "session": 1, "previous": None}, "a packet comes back exactly"

    assert reopened.save(latest) == 12, "a packet loaded back and saved unchanged is the same session"
    latest["next_action"] = "Rerun the burst test with --timeout 60"
    assert reopened.save(latest) == 13
    assert reopened.load(13) == {**latest, "session": 13, "previous": 12}, "save assigns session and previous itself"
    assert reopened.save(dict(PACKET, next_action="step 2")) == 14, "a packet like an older session is a new session"
    assert reopened.load(14)["previous"] == 13
    one_risk_closed = reopened.load(14)
    one_risk_closed["open_risks"] = one_risk_closed["open_risks"][1:]
    assert reopened.save(one_risk_closed) == 15, "any change to the packet is a new session"
    with pytest.raises(KeyError):
        reopened.load(16)
    stored = json.loads((root / "session-0015.json").read_text(encoding="utf-8"))
    assert stored == reopened.load(15) and stored["open_risks"] == PACKET["open_risks"][1:], "one JSON file per session"


DIFF = """\
diff --git a/app/signup.py b/app/signup.py
index 3f1c2aa..8d0e9b1 100644
--- a/app/signup.py
+++ b/app/signup.py
@@ -12,5 +12,6 @@ from app.limits import window
 def create_app():
     app = Flask(__name__)
-    print("booting")
-    app.register_blueprint(signup_bp)
+    app.register_blueprint(signup_bp)
+    app.register_blueprint(limits_bp)
+    app.register_blueprint(audit_bp)
     return app
@@ -40,4 +41,6 @@ def signup():
     body = request.get_json()
     print("signup", body["email"])
-    user = create_user(body)
+    if not window.allow(body["email"]):
+        print("limited", body["email"])
+    user = create_user(body)
     return user
diff --git a/app/limits/probe.py b/app/limits/probe.py
new file mode 100644
index 0000000..5b2c3d4
--- /dev/null
+++ b/app/limits/probe.py
@@ -0,0 +1,4 @@
+from pprint import pprint
+from app.limits import window
+
+pprint(window.state())
diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
@@ -3,1 +3,4 @@
 ## Rate limits
+```python
+print(window.allow("ana@example.com"))
+```
diff --git a/app/debug_dump.py b/app/debug_dump.py
deleted file mode 100644
index 9a8b7c6..0000000
--- a/app/debug_dump.py
+++ /dev/null
@@ -1,2 +0,0 @@
-print("dump")
-print(state)
"""
CLEAN_DIFF = """\
diff --git a/app/signup.py b/app/signup.py
index 3f1c2aa..8d0e9b1 100644
--- a/app/signup.py
+++ b/app/signup.py
@@ -12,5 +12,6 @@ from app.limits import window
 def create_app():
     app = Flask(__name__)
-    print("booting")
-    app.register_blueprint(signup_bp)
+    app.register_blueprint(signup_bp)
+    app.register_blueprint(limits_bp)
+    app.register_blueprint(audit_bp)
     return app
@@ -40,4 +41,5 @@ def signup():
     body = request.get_json()
     print("signup", body["email"])
-    user = create_user(body)
+    window.check(body["email"])
+    user = create_user(body)
     return user
diff --git a/app/limits/window.py b/app/limits/window.py
index 7a1b2c3..8d4e5f6 100644
--- a/app/limits/window.py
+++ b/app/limits/window.py
@@ -20,2 +20,3 @@ def report(window):
     rows = window.rows()
+    print_table(rows)
     return rows
"""
BURST_RISK = {"severity": "warn", "detail": "test_burst times out at 30 s", "test": "tests/test_signup.py::test_burst"}


def dirty_repo() -> RepoSnapshot:
    return RepoSnapshot(
        status=[" M app/signup.py", "R  app/limit.py -> app/limits/window.py", "?? notes/window.tmp", "?? scratch/"],
        stashes=[
            "stash@{0}: WIP on feat/signup-rate-limit: 4be1c0d add the limiter",
            "stash@{1}: On feat/signup-rate-limit: WIP on the burst test, see the open risk",
        ],
        files=[
            "README.md",
            "app/__init__.py",
            "app/scratchcard.py",
            "app/signup.py",
            "app/tmpl/signup.html",
            "app/limits/window.py",
            "app/limits/probe.py",
            "scratch/try_window.py",
            "scratch/out.tmp",
            "notes/window.tmp",
            "tools/scratch/bench.py",
            "build/out.tmp",
            "tests/test_signup.py",
        ],
        diff=DIFF,
        tests={
            "tests/test_signup.py::test_create_app": "passed",
            "tests/test_signup.py::test_burst": "failed",
            "tests/test_signup.py::test_burst_window": "failed",
            "tests/test_limits.py::test_import_window": "error",
            "tests/test_limits.py::test_slow_window": "skipped",
        },
        open_risks=[BURST_RISK, {"severity": "warn", "detail": "open blocker: awaiting a decision on the window"}],
        board={
            "project": "signup",
            "active": "signup-form",
            "features": [
                {"id": "signup-form", "status": "done"},
                {"id": "rate-limit", "status": "in_progress"},
                {"id": "captcha", "status": "in_progress"},
                {"id": "audit-log", "status": "todo"},
            ],
        },
        finished=["rate-limit", "audit-log"],
        branch=None,
        expected_branch="feat/signup-rate-limit",
        base_branch="main",
        branches={"main": True, "feat/signup-rate-limit": False, "wip/limiter-try": False, "fix/readme-typo": True},
    )


def clean_repo() -> RepoSnapshot:
    return RepoSnapshot(
        status=[],
        stashes=["stash@{0}: On feat/signup-rate-limit: WIP on the 60 s timeout, see the open risk"],
        files=["README.md", "app/scratchcard.py", "app/signup.py", "app/tmpl/signup.html", "app/limits/window.py"],
        diff=CLEAN_DIFF,
        tests={
            "tests/test_signup.py::test_create_app": "passed",
            "tests/test_signup.py::test_burst": "failed",
            "tests/test_limits.py::test_slow_window": "skipped",
        },
        open_risks=[BURST_RISK],
        board={
            "project": "signup",
            "active": "captcha",
            "features": [
                {"id": "signup-form", "status": "done"},
                {"id": "rate-limit", "status": "done"},
                {"id": "captcha", "status": "in_progress"},
            ],
        },
        finished=["rate-limit"],
        branch="feat/signup-rate-limit",
        expected_branch="feat/signup-rate-limit",
        base_branch="main",
        branches={"main": True, "feat/signup-rate-limit": False, "fix/readme-typo": True},
    )


@pytest.mark.skip("Part 3")
def test_clean_state() -> None:
    """The five cleanup checks find what would trip the next session, and nothing else."""
    issues = clean_state(dirty_repo())
    working_tree = [
        "uncommitted: app/signup.py",
        "uncommitted: app/limits/window.py",
        "uncommitted: notes/window.tmp",
        "uncommitted: scratch/",
        "stash without a note: stash@{0}",
    ]
    temp_files = ["scratch dir: scratch/", "temp file: notes/window.tmp", "scratch dir: tools/scratch/", "temp file: build/out.tmp"]
    debug_prints = ["debug print: app/signup.py:44", "debug print: app/limits/probe.py:4"]
    red_tests = ["red test: tests/test_signup.py::test_burst_window", "red test: tests/test_limits.py::test_import_window"]
    board = [
        "features in_progress at once: rate-limit, captcha",
        "finished feature not marked done: rate-limit",
        "finished feature not marked done: audit-log",
        "active feature is done: signup-form",
    ]
    branch = ["detached HEAD", "orphan branch: wip/limiter-try"]
    assert [i for i in issues if i.startswith(("uncommitted", "stash"))] == working_tree, (
        "every change is committed, or stashed with a note"
    )
    assert [i for i in issues if i.startswith(("scratch dir", "temp file"))] == temp_files, (
        "*.tmp files and scratch directories"
    )
    assert [i for i in issues if i.startswith("debug print")] == debug_prints, (
        "debug prints among the lines this session added, at their new line numbers"
    )
    assert [i for i in issues if i.startswith("red test")] == red_tests, (
        "a red test blocks unless an open risk names exactly that test"
    )
    assert [i for i in issues if i.startswith(("features", "finished", "active"))] == board, (
        "the feature board matches what happened"
    )
    assert [i for i in issues if i.startswith(("detached", "wrong branch", "orphan"))] == branch, (
        "on the expected branch, and no stray branches"
    )
    assert issues == working_tree + temp_files + debug_prints + red_tests + board + branch, (
        "one issue per problem, the checks in the table's order"
    )

    assert clean_state(clean_repo()) == [], "a clean workbench has no blocking issue"
    assert clean_state(dataclasses.replace(clean_repo(), branch="main")) == [
        "wrong branch: main (expected feat/signup-rate-limit)"
    ]
    snapshot = WorkbenchSnapshot("T-014", dict(STATE), dict(VERDICT), None, [], {"touched": []})
    with pytest.raises(DirtyWorkbench) as refused:
        generate_handoff(snapshot, clean_state=issues)
    assert refused.value.issues == issues, "no packet while the workbench is dirty"


def ok(command_id: str) -> dict:
    return {"command_id": command_id, "command": ["pytest", "-q"], "exit_code": 0}


def bad(command_id: str, exit_code) -> dict:
    return {"command_id": command_id, "command": ["pytest", "tests/test_signup.py"], "exit_code": exit_code}


def parse(lines) -> list[dict]:
    return [json.loads(line) for line in "".join(lines).splitlines()]


class Rec(dict):
    """A feedback record that counts how many records are alive, to see what trim_stream holds on to."""

    alive = 0
    peak = 0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        Rec.alive += 1
        Rec.peak = max(Rec.peak, Rec.alive)

    def __del__(self) -> None:
        Rec.alive -= 1


def feedback_log(n: int, exit_code, pulled: list[int]):
    """A feedback log of n records, read one record at a time."""
    for i in range(n):
        pulled.append(i)
        yield Rec(command_id=f"c{i:06d}", command=["pytest", "-q", f"tests/test_window.py::test_{i}"], exit_code=exit_code(i))


@pytest.mark.skip("Part 4")
def test_trim_stream() -> None:
    """One pass over a log of any length: every failure and the last k, in log order, never the whole log in memory."""
    log = [ok("c1"), bad("c2", 1), ok("c3"), ok("c4"), bad("c5", None), ok("c6"), bad("c7", -9), ok("c8")]
    assert parse(trim_stream(iter(log), k=3)) == [log[1], log[4], log[5], log[6], log[7]], (
        "every failure plus the last k, in log order, a failure among the last k once"
    )
    first_two_pass = [ok("c1"), ok("c2"), bad("c3", 1)]
    assert parse(trim_stream(iter(first_two_pass), k=3)) == first_two_pass, "a failure among the last k keeps its place"
    assert parse(trim_stream(iter(log), k=0)) == [log[1], log[4], log[6]], "k=0 keeps the failures only"
    assert parse(trim_stream(iter(log[:2]), k=5)) == log[:2]
    assert list(trim_stream(iter([]), k=5)) == []

    pulled: list[int] = []
    stream = trim_stream(feedback_log(100_000, lambda i: 1 if i == 0 else 0, pulled), k=5)
    assert json.loads(next(stream))["command_id"] == "c000000"
    assert len(pulled) <= 6, "a failure is written as soon as it leaves the last k"
    stream.close()

    def exit_code(i: int):
        if i % 1000 == 7:
            return None
        return 1 if i % 10 == 3 else 0

    start = Rec.peak = Rec.alive
    written = parse(trim_stream(feedback_log(50_000, exit_code, pulled), k=5))
    assert [entry["command_id"] for entry in written[:3]] == ["c000003", "c000007", "c000013"]
    assert len(written) == 5055 and written[-1]["command_id"] == "c049999", "5,050 failures and the last 5 records"
    assert Rec.peak - start <= 8, "hold the last k records, not the log and not its failures"


def risk(risk_id: str, severity: str, detail: str) -> dict:
    return {"id": risk_id, "severity": severity, "detail": detail}


def packet(session, previous, branch, next_action, opened=(), closed=()) -> dict:
    return {
        "session": session,
        "previous": previous,
        "branch": branch,
        "next_action": next_action,
        "open_risks": [dict(r) for r in opened],
        "closed_risks": list(closed),
    }


WINDOW = risk("R-1", "warn", "rate-limit window not decided")
BURST = risk("R-2", "block", "test_burst times out")
README = risk("R-3", "warn", "README.md changed off-scope")
BURST_AGAIN = risk("R-2", "warn", "test_burst times out at 30 s, passes with --timeout 60")
JSON_429 = risk("R-4", "warn", "the 429 response body is not JSON")
CAPTCHA = risk("R-5", "warn", "captcha copy not reviewed")
WINDOW_AGAIN = risk("R-1", "warn", "window decided (5 per minute) but not load-tested")
OLD_ENDPOINT = risk("R-6", "block", "the signup form still posts to /v1/signup")
PACKETS = [
    packet(1, None, "main", "Write the limiter", [WINDOW, BURST]),
    packet(2, 1, "main", "Make test_burst pass", [README]),
    packet(3, 2, "main", "Split the API and UI work", [BURST_AGAIN], ["R-1"]),
    packet(4, 3, "feat/signup-api", "Return JSON from the 429 handler", [JSON_429], ["R-3"]),
    packet(5, 3, "feat/signup-ui", "Wire the captcha", [CAPTCHA]),
    packet(6, 4, "feat/signup-api", "Load-test the window", [WINDOW_AGAIN], ["R-2"]),
    packet(7, 5, "feat/signup-ui", "Review the captcha copy"),
    packet(8, 3, "feat/signup-ui", "Point the form at /v2/signup", [OLD_ENDPOINT]),
]


@pytest.mark.skip("Part 5")
def test_branch_heads() -> None:
    """Each branch's latest handoff, with the risks its own chain still carries."""
    shuffled = [PACKETS[i] for i in (5, 2, 7, 0, 4, 1, 6, 3)]
    given = copy.deepcopy(shuffled)
    heads = branch_heads(shuffled)
    assert [(head.branch, head.session) for head in heads] == [
        ("main", 3),
        ("feat/signup-api", 6),
        ("feat/signup-ui", 8),
    ], "one head per branch, its highest session, ordered by session"
    main, api, ui = heads
    assert (main.lineage, api.lineage, ui.lineage) == ([1, 2, 3], [1, 2, 3, 4, 6], [1, 2, 3, 8]), (
        "a branch forked from another one inherits the sessions before the fork"
    )
    assert main.open_risks == [BURST_AGAIN, README], (
        "risks carry over until a session closes them; a risk is matched by id, and new wording replaces it in place"
    )
    assert ui.open_risks == [BURST_AGAIN, README, OLD_ENDPOINT], (
        "only the head's own chain counts: closing a risk on one branch leaves it open on another"
    )
    assert api.open_risks == [JSON_429, WINDOW_AGAIN], "closed risks drop out, and a reopened one goes to the end"
    assert ui == BranchHead("feat/signup-ui", 8, "Point the form at /v2/signup", [BURST_AGAIN, README, OLD_ENDPOINT], [1, 2, 3, 8]), (
        "a head carries its own next_action"
    )
    assert [head.next_action for head in heads] == [
        "Split the API and UI work",
        "Load-test the window",
        "Point the form at /v2/signup",
    ]
    assert shuffled == given, "the packets are left as they came"

    for missing in (4, 5):
        with pytest.raises(BrokenChain) as broken:
            branch_heads([p for p in PACKETS if p["session"] != missing])
        assert re.search(rf"\b{missing}\b", str(broken.value)), "BrokenChain names the missing session"
    with pytest.raises(BrokenChain):
        branch_heads([packet(1, 0, "main", "Write the limiter")])
    with pytest.raises(ValueError):
        branch_heads(PACKETS + [packet(5, 3, "feat/signup-ui", "Wire the captcha again")])
    with pytest.raises(ValueError):
        branch_heads([packet(1, None, "main", "a"), packet(2, 3, "main", "b"), packet(3, None, "spike", "c")])
    with pytest.raises(ValueError):
        branch_heads([packet(1, None, "main", "a"), packet(2, 2, "spike", "b"), packet(3, 1, "spike", "c")])
    assert branch_heads([]) == []
