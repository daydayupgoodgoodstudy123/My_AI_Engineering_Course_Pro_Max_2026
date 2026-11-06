import asyncio
import csv
import json
import time

import pytest
from swebench.gaia import Difficulty, gaia_level
from swebench.harness import Outcome, Patch, Task, TaskResult, run_task, run_tests
from swebench.report import added_lines, leaks, nearest_rank, report
from swebench.service import BenchmarkRun
from swebench.store import ResultStore, TaskRecord
from swebench.stream import AgentRun, evaluate_stream


def edit(**changes):
    """A toy patch: set nested keys in place, the way an edit touches one file of the repo."""

    def apply(state):
        for path, value in changes.items():
            *parents, leaf = path.split("__")
            node = state
            for key in parents:
                node = node[key]
            node[leaf] = value
        return state

    return apply


@pytest.mark.skip("Part 1")
def test_harness_gate() -> None:
    """A patch resolves a task only when FAIL_TO_PASS flips and PASS_TO_PASS holds, test by test."""
    counter = Task(
        "demo__counter-1",
        "Counter has no reset value; add counter.reset_to = 0.",
        {"counter": {"value": 3, "step": 1}},
        {
            "tests/test_counter.py::test_reset": lambda s: s["counter"]["reset_to"] == 0,
            "tests/test_counter.py::test_step": lambda s: s["counter"]["step"] == 1,
        },
        ["tests/test_counter.py::test_reset"],
        ["tests/test_counter.py::test_step"],
    )
    result = run_task(counter, Patch("+reset_to = 0\n", edit(counter__reset_to=0)))
    assert result == TaskResult(
        "demo__counter-1", "resolved", 1, 1, 1, 1,
        [
            Outcome("tests/test_counter.py::test_reset", "before", False),
            Outcome("tests/test_counter.py::test_step", "before", True),
            Outcome("tests/test_counter.py::test_reset", "after", True),
            Outcome("tests/test_counter.py::test_step", "after", True),
        ],
    ), "a test that raises is a failing test, not a broken run"
    assert counter.state == {"counter": {"value": 3, "step": 1}}, "the task's own state never changes"
    assert run_tests(counter.tests, counter.state) == (
        "ERROR tests/test_counter.py::test_reset\nPASSED tests/test_counter.py::test_step\n"
    ), "a test that raises is reported as ERROR"

    widened = run_task(
        counter, Patch("+reset_to = 0\n-step = 1\n+step = 2\n", edit(counter__reset_to=0, counter__step=2))
    )
    assert widened == TaskResult(
        "demo__counter-1", "unresolved", 1, 1, 0, 1,
        [
            Outcome("tests/test_counter.py::test_reset", "before", False),
            Outcome("tests/test_counter.py::test_step", "before", True),
            Outcome("tests/test_counter.py::test_reset", "after", True),
            Outcome("tests/test_counter.py::test_step", "after", False),
        ],
    ), "a patch that breaks a PASS_TO_PASS test is unresolved"
    regressed = run_task(counter, Patch("-step = 1\n+step = 2\n", edit(counter__step=2)))
    assert (regressed.status, regressed.ftp_passed, regressed.ptp_passed) == ("unresolved", 0, 0), (
        "the pass counts are taken after the patch"
    )

    text = Task(
        "demo__text-7",
        "strip() leaves trailing whitespace.",
        {"sep": " ", "strip": False},
        {
            "tests/test_text.py::test_split_lines": lambda s: True,
            "tests/test_text.py::test_split": lambda s: s["sep"] == " ",
            "tests/test_text.py::test_strip[two words]": lambda s: s["strip"],
            "tests/test_text.py::test_strip[word  ]": lambda s: s["strip"],
        },
        ["tests/test_text.py::test_strip[two words]", "tests/test_text.py::test_strip[word  ]"],
        ["tests/test_text.py::test_split_lines", "tests/test_text.py::test_split"],
    )
    overreach = run_task(text, Patch("", edit(strip=True, sep=",")))
    assert (overreach.status, overreach.ftp_passed, overreach.ptp_passed) == ("unresolved", 2, 1), (
        "a test passes only when its own id is reported PASSED"
    )
    clean = run_task(text, Patch("", edit(strip=True)))
    assert (clean.status, clean.ftp_passed, clean.ptp_passed) == ("resolved", 2, 2), (
        "a test passes only when its own id is reported PASSED"
    )

    def no_op(state):
        return state

    already = Task("demo__noop-2", "", {"x": 1}, {"t.py::a": lambda s: s["x"] == 1, "t.py::b": lambda s: True},
                   ["t.py::a"], ["t.py::b"])
    broken = Task("demo__broken-3", "", {"x": 0}, {"t.py::a": lambda s: s["x"] == 1, "t.py::b": lambda s: False},
                  ["t.py::a"], ["t.py::b"])
    untested = Task("demo__none-4", "", {"x": 0}, {"t.py::b": lambda s: True}, [], ["t.py::b"])
    invalid = run_task(already, Patch("", no_op))
    assert invalid == TaskResult(
        "demo__noop-2", "invalid", 0, 1, 0, 1,
        [Outcome("t.py::a", "before", True), Outcome("t.py::b", "before", True)],
    ), "a task whose tests do not hold before the patch is invalid"
    assert run_task(broken, Patch("", edit(x=1))).status == "invalid", (
        "a task whose tests do not hold before the patch is invalid"
    )
    mixed = {"t.py::a": lambda s: s["x"] == 1, "t.py::b": lambda s: True, "t.py::c": lambda s: 1 / s["x"] > 0,
             "t.py::d": lambda s: True}
    for ftp, ptp in ((["t.py::a", "t.py::b"], ["t.py::d"]), (["t.py::a"], ["t.py::d", "t.py::c"])):
        half = Task("demo__half-5", "", {"x": 0}, mixed, ftp, ptp)
        assert run_task(half, Patch("", edit(x=1))).status == "invalid", (
            "a task whose tests do not hold before the patch is invalid"
        )
    assert run_task(untested, Patch("", no_op)).status == "invalid", "a task with no FAIL_TO_PASS test is invalid"

    def crash(state):
        raise RuntimeError("patch does not apply")

    assert run_task(counter, Patch("", crash)).status == "error", "a patch that raises is an error"
    assert run_task(already, Patch("", crash)).status == "invalid", "an invalid task never has its patch applied"

    n = 3500
    big = Task(
        "django__django-99999",
        "",
        {"fixed": False},
        {**{f"tests/test_bulk.py::test_case[{i:05d}]": (lambda s: True) for i in range(n)},
         "tests/test_bulk.py::test_fix": lambda s: s["fixed"]},
        ["tests/test_bulk.py::test_fix"],
        [f"tests/test_bulk.py::test_case[{i:05d}]" for i in range(n)],
    )
    start = time.perf_counter()
    graded = run_task(big, Patch("", edit(fixed=True)))
    elapsed = time.perf_counter() - start
    assert graded.status == "resolved" and graded.ptp_passed == n
    assert elapsed < 0.1, "run_task should be fast on large test suites"


@pytest.mark.skip("Part 2")
def test_result_store(tmp_path) -> None:
    """Task records survive a round trip through the CSV files, including a reopen."""
    root = tmp_path / "run-1"
    patch = (
        "--- a/src/fmt.py\r\n+++ b/src/fmt.py\r\n@@ -1,2 +1,2 @@\r\n"
        "-SEP = 'a,b'\r\n+SEP = \"a, b\"  \r\n \r\n"
    )
    first = TaskRecord(
        "sphinx-doc__sphinx-8721", "resolved", patch, 18234, 95112, 23,
        [
            Outcome("tests/test_fmt.py::test_join[a, b]", "before", False),
            Outcome('tests/test_fmt.py::test_quote["x"]', "before", True),
            Outcome("tests/test_fmt.py::test_join[a, b]", "after", True),
            Outcome('tests/test_fmt.py::test_quote["x"]', "after", True),
        ],
    )
    crashed = TaskRecord("django__django-11099", "error", "", 0, 3, 1, [])

    store = ResultStore(root)
    store.add(first)
    store.add(crashed)
    assert store.get("sphinx-doc__sphinx-8721") == first, "a record must round-trip exactly"
    with pytest.raises(KeyError):
        store.get("no-such-task")

    reopened = ResultStore(root)
    assert reopened.records() == [first, crashed], "a reopened store sees earlier records, in order"
    assert reopened.get("sphinx-doc__sphinx-8721") == first, "a reopened store sees earlier records, in order"
    loaded = reopened.records()
    assert all(type(v) is int for r in loaded for v in (r.tokens, r.wall_ms, r.steps)), "costs come back as ints"
    assert all(type(o.passed) is bool for o in loaded[0].outcomes), "passed comes back as a bool"
    outcomes = [
        Outcome("t.py::a", "before", False), Outcome("t.py::a", "after", True), Outcome("t.py::b", "after", False),
    ]
    with pytest.raises(ValueError):
        reopened.add(TaskRecord("django__django-11099", "resolved", "", 1, 1, 1, outcomes))

    bad = TaskRecord(
        "sympy__sympy-20590", "unresolved", "+x\n", 900, 4100, 7,
        [Outcome("t.py::a", "before", False), Outcome("t.py::a", "after", True), Outcome("t.py::b", "during", True)],
    )
    with pytest.raises(ValueError):
        reopened.add(bad)
    for status, tokens in (("unresolved", 900.0), ("unresolved", -1), ("fixed", 900)):
        with pytest.raises(ValueError):
            reopened.add(TaskRecord("sympy__sympy-20590", status, "+x\n", tokens, 4100, 7, outcomes))
    good = TaskRecord("sympy__sympy-20590", "unresolved", "+x\n", 900, 4100, 7, outcomes)
    reopened.add(good)
    assert ResultStore(root).records() == [first, crashed, good], "a rejected record leaves nothing behind"

    with open(root / "tests.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [["instance_id", "test_id", "phase", "passed"]] + [
        [r.instance_id, o.test_id, o.phase, "1" if o.passed else "0"]
        for r in (first, crashed, good)
        for o in r.outcomes
    ], "tests.csv has one header and one row per test outcome"
    with open(root / "runs.csv", newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == ["instance_id", "status", "tokens", "wall_ms", "steps", "patch"]


def record(iid: str, status: str, patch: str = "", tokens: int = 0, steps: int = 0, wall_ms: int = 0) -> TaskRecord:
    return TaskRecord(iid, status, patch, tokens, wall_ms, steps, [])


ISSUE = "counter is off by one. I think the fix is:\n    return  count +\t1\nin utils.py\n"
LEAKY = (
    "--- a/utils.py\n+++ b/utils.py\n@@ -1,2 +1,4 @@\n def counter(count):\n-    return count\n"
    "+    # fix off-by-one\n+\n+    return count + 1\n+    # see issue\n"
)


@pytest.mark.skip("Part 3")
def test_report_views(tmp_path) -> None:
    """Report the run three ways, with percentiles instead of a single number."""
    assert leaks(ISSUE, LEAKY), "an added line leaks when it matches an issue line, ignoring whitespace"
    prose = "Should we pass the value through? Then return None from it )\n"
    assert not leaks(prose, "+pass\n+return None\n+)\n"), "a leaking line must match a whole issue line"
    lines = [f"+line_{i} = {i}\n" for i in range(10)]
    issue = "".join(f"line_{i} = {i}\n" for i in range(3))
    assert leaks(issue, "".join(lines)), "3 of 10 added lines is enough to leak"
    assert not leaks(issue, "".join(lines) + "+line_10 = 10\n"), "3 of 11 is not"
    assert not leaks(ISSUE, "--- a/x.py\n+++ b/x.py\n-gone\n"), "a patch that adds nothing does not leak"
    assert added_lines("+++ b/f.py\n-x = 0\n+x  =\t1  \n+ \t\n y = 2\n") == ["x = 1"], (
        "an added line keeps its words, with each run of whitespace collapsed to one space"
    )

    steps = [3, 5, 4, 12, 7, 6, 25, 4, 5, 8]
    assert [nearest_rank(steps, p) for p in (50, 75, 95)] == [5, 8, 25], "nearest rank, no interpolation"
    assert nearest_rank(steps, 0) == 3, "the nearest rank is at least the 1st"
    assert nearest_rank([42], 50) == 42 and nearest_rank([], 50) is None

    records = [
        record("a__a-1", "resolved", LEAKY, 100, 3, 1000),
        record("a__a-2", "resolved", "+fresh = 1\n", 200, 5, 2000),
        record("a__a-3", "unresolved", LEAKY, 300, 4, 3000),
        record("a__a-4", "error", "", 400, 12, 4000),
        record("a__a-5", "invalid", "", 9999, 99, 99999),
        record("a__a-6", "resolved", "+fresh = 2\n", 500, 7, 5000),
    ]
    issues = {r.instance_id: ISSUE for r in records}
    got = report(records, issues, verified={"a__a-2", "a__a-3", "a__a-5"})
    assert got["all"] == {
        "tasks": 5, "resolved": 3, "rate": 3 / 5,
        "tokens": {"p50": 300, "p75": 400, "p95": 500},
        "steps": {"p50": 5, "p75": 7, "p95": 12},
        "wall_ms": {"p50": 3000, "p75": 4000, "p95": 5000},
    }, "invalid tasks are not scored; errors count against the agent"
    assert got["verified"] == {
        "tasks": 2, "resolved": 1, "rate": 1 / 2,
        "tokens": {"p50": 200, "p75": 300, "p95": 300},
        "steps": {"p50": 4, "p75": 5, "p95": 5},
        "wall_ms": {"p50": 2000, "p75": 3000, "p95": 3000},
    }, "verified covers only the Verified tasks"
    assert got["plus"] == {**got["all"], "resolved": 2, "rate": 2 / 5}, (
        "a leaked fix counts as unresolved, and stays in the denominator"
    )
    empty = report(records, issues, verified=set())["verified"]
    assert empty == {"tasks": 0, "resolved": 0, "rate": None, "tokens": None, "steps": None, "wall_ms": None}, (
        "an empty view has no rate"
    )

    tasks = [
        Task("lesson__t001", "fix off-by-one in counter", {"counter": 0, "multiplier": 2},
             {"t::counter": lambda s: s["counter"] > 0, "t::multiplier": lambda s: s["multiplier"] == 2},
             ["t::counter"], ["t::multiplier"]),
        Task("lesson__t002", "fix multiplier regression", {"counter": 1, "multiplier": 0},
             {"t::multiplier": lambda s: s["multiplier"] > 0, "t::counter": lambda s: s["counter"] == 1},
             ["t::multiplier"], ["t::counter"]),
        Task("lesson__t003", "agent overreaches", {"counter": 1, "multiplier": 2, "flag": True},
             {"t::counter": lambda s: s["counter"] > 1, "t::flag": lambda s: s["flag"],
              "t::multiplier": lambda s: s["multiplier"] == 2},
             ["t::counter"], ["t::flag", "t::multiplier"]),
    ]
    run = BenchmarkRun(ResultStore(tmp_path / "run"), tasks, verified={"lesson__t001"})
    run.submit("lesson__t001", AgentRun(Patch("+counter += 1\n", edit(counter=1)), 120, 4), wall_ms=800)
    run.submit("lesson__t002", AgentRun(Patch("+multiplier = 2\n", edit(multiplier=2)), 210, 6), wall_ms=1500)
    run.submit("lesson__t003", AgentRun(Patch("+counter = 2\n", edit(counter=2, flag=False)), 340, 9), wall_ms=2100)
    summary = run.report()
    assert (summary["all"]["rate"], summary["verified"]["rate"]) == (2 / 3, 1.0), "grade, store and report end to end"


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(asyncio.wait_for(drain(), 3))


def bug_task(iid: str, already_fixed: bool = False) -> Task:
    return Task(
        iid,
        f"issue for {iid}",
        {"bug": not already_fixed},
        {"t.py::test_fix": lambda s: not s["bug"], "t.py::test_keep": lambda s: True},
        ["t.py::test_fix"],
        ["t.py::test_keep"],
    )


class FakeAgent:
    """A scripted model: it thinks for a number of event-loop turns, then hands back a patch."""

    def __init__(self, script: dict[str, tuple[int, str]]) -> None:
        self.script = script
        self.running = 0
        self.peak = 0
        self.finished: list[str] = []
        self.cancelled: list[str] = []

    async def __call__(self, task: Task) -> AgentRun:
        turns, kind = self.script[task.instance_id]
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            for _ in range(turns):
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            self.cancelled.append(task.instance_id)
            raise
        finally:
            self.running -= 1
        self.finished.append(task.instance_id)
        if kind == "raise":
            raise RuntimeError("rate limited")
        return AgentRun(Patch(f"+bug = {kind != 'fix'}\n", edit(bug=kind != "fix")), 100 * turns, turns)


SCRIPT = {"a": (50, "fix"), "b": (1, "fix"), "c": (1, "raise"), "d": (3, "keep"), "e": (1, "fix")}


@pytest.mark.skip("Part 4")
def test_stream_results() -> None:
    """Grade tasks concurrently and stream one JSON line per task as it finishes."""
    tasks = [bug_task(iid, already_fixed=(iid == "e")) for iid in "abcde"]
    agent = FakeAgent(SCRIPT)
    finished_at_first: list[str] = []

    async def read_all() -> list[str]:
        out = []
        async for line in evaluate_stream(tasks, agent, concurrency=2):
            if not out:
                finished_at_first.extend(agent.finished)
            out.append(line)
        return out

    lines = asyncio.run(asyncio.wait_for(read_all(), 3))
    events = [json.loads(line) for line in "".join(lines).splitlines()]
    assert events == [
        {"instance_id": "b", "status": "resolved", "fail_to_pass": [1, 1], "pass_to_pass": [1, 1],
         "tokens": 100, "steps": 1, "error": None},
        {"instance_id": "c", "status": "error", "fail_to_pass": [0, 1], "pass_to_pass": [0, 1],
         "tokens": None, "steps": None, "error": "RuntimeError: rate limited"},
        {"instance_id": "d", "status": "unresolved", "fail_to_pass": [0, 1], "pass_to_pass": [1, 1],
         "tokens": 300, "steps": 3, "error": None},
        {"instance_id": "e", "status": "invalid", "fail_to_pass": [0, 1], "pass_to_pass": [0, 1],
         "tokens": 100, "steps": 1, "error": None},
        {"instance_id": "a", "status": "resolved", "fail_to_pass": [1, 1], "pass_to_pass": [1, 1],
         "tokens": 5000, "steps": 50, "error": None},
        {"summary": {"resolved": 2, "unresolved": 1, "invalid": 1, "error": 1}},
    ], "one line per task in the order they finish, then the summary"
    assert lines[0] == (
        '{"instance_id": "b", "status": "resolved", "fail_to_pass": [1, 1], "pass_to_pass": [1, 1], '
        '"tokens": 100, "steps": 1, "error": null}\n'
    ), "keys in the documented order, one line per item"
    assert len(lines) == 6 and all(line.count("\n") == 1 for line in lines), "one line per item"
    assert agent.peak == 2, "run up to `concurrency` agents at a time, never more"
    assert "a" not in finished_at_first, "emit each task's line as soon as it is graded"

    closing = FakeAgent(SCRIPT)

    async def first_then_close():
        stream = evaluate_stream(tasks, closing, concurrency=2)
        first = await stream.__anext__()
        await stream.aclose()
        return first, [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    first, leftover = asyncio.run(first_then_close())
    assert json.loads(first)["instance_id"] == "b"
    assert "a" in closing.cancelled and closing.running == 0 and leftover == [], (
        "closing the stream cancels the running agents"
    )

    assert collect(evaluate_stream([], agent, concurrency=2)) == [
        '{"summary": {"resolved": 0, "unresolved": 0, "invalid": 0, "error": 0}}\n'
    ], "an empty run still ends with the summary"
    with pytest.raises(ValueError):
        collect(evaluate_stream(tasks, agent, concurrency=0))


def call(tool: str, modality: str) -> dict:
    return {"tool": tool, "input": modality}


WEB = call("search", "web")


@pytest.mark.skip("Part 5")
def test_gaia_levels() -> None:
    """Level a GAIA-style question by its decomposition tree."""
    assert gaia_level({"think": "recall the capital of France"}) == Difficulty(1, 0, ()), (
        "a question with no tool call is level 1 with an empty chain"
    )
    assert gaia_level([WEB, {"think": "read off the first author"}]) == Difficulty(1, 1, ("web",))
    assert gaia_level({"par": [WEB, WEB, WEB]}) == Difficulty(1, 1, ("web",)), "parallel branches do not add up"
    assert gaia_level([{"think": "a"}, WEB, {"think": "b"}, {"par": [{"think": "c"}, {"think": "d"}]}]) == (
        Difficulty(1, 1, ("web",))
    ), "a reasoning step is not a tool call"
    assert gaia_level([WEB, call("visit", "web"), {"think": "read off the first author"}]) == (
        Difficulty(2, 2, ("web",))
    ), "a chain of two tool calls is level 2"
    assert gaia_level({"seq": [WEB, call("read_pdf", "pdf")]}) == Difficulty(2, 2, ("pdf", "web")), (
        "calls in a seq add up; each modality is listed once, sorted"
    )
    assert gaia_level({"par": [WEB, call("transcribe", "audio")]}) == Difficulty(2, 1, ("audio", "web")), (
        "two modalities anywhere in the plan make level 2"
    )

    react = [
        call("visit", "web"),
        call("read_pdf", "pdf"),
        call("visit", "web"),
        call("list_issues", "web"),
        call("list_issues", "web"),
        {"think": "bugs / total issues"},
    ]
    assert gaia_level(react) == Difficulty(3, 5, ("pdf", "web")), "a long tool chain across modalities is level 3"
    hidden = {"par": [[WEB] * 6, [WEB, WEB, WEB, WEB, call("read_image", "image")]]}
    assert gaia_level(hidden) == Difficulty(3, 6, ("image", "web")), (
        "level 3 can sit on a path shorter than the longest one"
    )
    split = [WEB, {"par": [call("read_image", "image"), [WEB, WEB]]}, WEB, WEB]
    assert gaia_level(split) == Difficulty(2, 5, ("image", "web")), (
        "the 5 calls and the 2 modalities must be on one path"
    )

    for bad in ([], {"seq": []}, {"par": []}, {"tool": "search"}, {"step": "?"}, "search the web",
                {"seq": [WEB], "par": [WEB]}, [WEB, 42]):
        with pytest.raises(ValueError):
            gaia_level(bad)
