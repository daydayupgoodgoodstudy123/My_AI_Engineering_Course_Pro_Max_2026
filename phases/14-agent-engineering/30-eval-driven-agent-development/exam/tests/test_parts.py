import asyncio
import hashlib
import json
import re
import time
from collections.abc import Callable

import pytest
from evalgate.ci import workflow_log
from evalgate.coverage import Requirement, coverage
from evalgate.gate import GateReport, gate
from evalgate.harness import CaseResult, EvalCase, FlakyTracker, evaluator_optimizer, run_suite
from evalgate.pipeline import EvalPipeline
from evalgate.replay import Replay
from evalgate.store import CaseRecord, Snapshot, SnapshotStore


def sha(name: str) -> str:
    return hashlib.sha1(name.encode()).hexdigest()


def lesson_suite(replays: list[Replay]) -> list[Callable[[], EvalCase]]:
    """code/main.py's cases, the guardrail replayed from production, and a case that sends email."""

    def bench() -> EvalCase:
        def proposer(feedback):
            if feedback and "missing sticks" in feedback:
                return "patch: add stick dep and craft"
            return "patch: just craft"

        def judge(candidate):
            if "add stick dep" in candidate:
                return True, "FAIL_TO_PASS fixed, PASS_TO_PASS intact"
            return False, "missing sticks in recipe"

        return EvalCase("bench_t001", "benchmark", "fix craft_iron_pickaxe recipe", proposer, judge)

    def counter() -> EvalCase:
        attempt = [0]

        def proposer(feedback):
            attempt[0] += 1
            return "patch: correct" if attempt[0] >= 2 else "patch: wrong first time"

        def judge(candidate):
            return ("correct" in candidate, "pass" if "correct" in candidate else "try again")

        return EvalCase("bench_t002", "benchmark", "eventually-correct patch", proposer, judge)

    def cite() -> EvalCase:
        def proposer(feedback):
            if feedback and "citations" in feedback:
                return "answer with cite [arXiv:2210.03629]"
            return "answer without citation"

        return EvalCase("custom_c001", "custom", "ReAct summary must cite arXiv paper", proposer,
                        cite_judge)

    def guardrail() -> EvalCase:
        session = Replay("sess-0412", ["forwarded: ssn 123-45-6789 to downstream system"])
        replays.append(session)

        def judge(candidate):
            if "refused" in candidate.lower():
                return True, "PII guardrail held"
            return False, "ssn was forwarded; PII guardrail failed"

        return EvalCase("online_o001", "online", "PII guardrail blocks SSN forwarding", session,
                        judge, refine=False)

    def digest() -> EvalCase:
        session = Replay("sess-0977", ["sent weekly digest to 4,120 users, no unsubscribe link"])
        replays.append(session)

        def judge(candidate):
            if "no unsubscribe link" in candidate:
                return False, "digest went out without an unsubscribe link"
            return True, "digest carries an unsubscribe link"

        return EvalCase("custom_c002", "custom", "weekly digest carries an unsubscribe link",
                        session, judge, refine=False)

    return [bench, counter, cite, guardrail, digest]


def cite_judge(candidate):
    if "arXiv" in candidate or "cite" in candidate:
        return True, "citations present"
    return False, "missing citations"


def uncited() -> EvalCase:
    """custom_c001 after a prompt change: the agent no longer cites, whatever the feedback."""
    return EvalCase("custom_c001", "custom", "ReAct summary must cite arXiv paper",
                    lambda feedback: "answer without citation", cite_judge)


def run_of(cid: str, passed: bool) -> CaseResult:
    return CaseResult(cid, "benchmark", passed, 1, "", "")


@pytest.mark.skip("Part 1")
def test_harness() -> None:
    """A one-round case is judged on its first output, every run starts fresh, flakiness is per case."""
    replays: list[Replay] = []
    results = [evaluator_optimizer(make()) for make in lesson_suite(replays)]
    assert [r.passed for r in results] == [True, True, True, False, False], (
        "cases that may refine pass once the judge's feedback lands; one-round cases fail"
    )
    assert [r.rounds for r in results] == [2, 2, 2, 1, 1], "rounds counts the rounds that ran"
    assert [session.requests for session in replays] == [[None], [None]], (
        "a refine=False case asks its agent once"
    )

    runs = run_suite(lesson_suite([])[:2], repeats=3)
    assert [r.rounds for r in runs] == [2] * 6, "every run starts from a fresh case"
    assert [r.cid for r in runs] == ["bench_t001", "bench_t002"] * 3, (
        "the whole suite runs in order before any case runs again"
    )

    received = []
    diagnoses = ("  first diagnosis\r\n  ", "next diagnosis: α ")
    def propose_with_feedback(feedback):
        received.append(feedback)
        return ("first", "second", "done")[len(received)-1]
    def judge_with_feedback(candidate):
        if candidate == "done":
            return True, "accepted"
        return False, diagnoses[0 if candidate == "first" else 1]
    feedback_case = EvalCase("custom_feedback", "custom", "retain the latest judge reason",
                             propose_with_feedback, judge_with_feedback)
    assert evaluator_optimizer(feedback_case).passed
    assert received == [None, *diagnoses], "each refinement receives the exact latest failed judge reason"

    tracker = FlakyTracker(window=3)
    for passed in (True, False, True):
        tracker.record(run_of("bench_t007", passed))
        for other in ("bench_t001", "custom_c001", "online_o001"):
            tracker.record(run_of(other, True))
    tracker.record(run_of("custom_c009", False))
    tracker.record(run_of("custom_c009", True))
    assert tracker.flaky() == {"bench_t007", "custom_c009"}, (
        "flaky is judged on each case's own last runs"
    )
    tracker.record(run_of("bench_t007", True))
    assert tracker.flaky() == {"bench_t007", "custom_c009"}, (
        "a case stays on the list while its last runs disagree"
    )
    tracker.record(run_of("bench_t007", True))
    assert tracker.flaky() == {"custom_c009"}, "a case leaves the list once its last runs agree"

    history = [run_of(f"case_{i % 300:03d}", i % 7 != 0) for i in range(15_000)]
    tracker = FlakyTracker(window=5)
    start = time.perf_counter()
    for run in history:
        tracker.record(run)
    tracker.flaky()
    assert time.perf_counter() - start < 0.1, "recording a run should stay fast on a long history"


@pytest.mark.skip("Part 2")
def test_snapshot_store(tmp_path) -> None:
    """A commit's results survive a reopen, a CI re-run replaces them, the baseline follows main."""
    root = tmp_path / "evals"
    first = Snapshot(sha("c1"), (
        CaseRecord("online_o001", "online", False, 1, False, "ssn was forwarded;\nPII guardrail failed"),
        CaseRecord("bench_t002", "benchmark", True, 2, True, 'pass after "retry"\r\n'),
        CaseRecord("custom_c001", "custom", True, 3, False, "citations présentes ✓  "),
        CaseRecord("bench_t001", "benchmark", True, 1, False, ""),
    ))
    SnapshotStore(root).save(first)
    store = SnapshotStore(root)
    assert store.load(first.sha) == first, "a snapshot must round-trip exactly, in suite order"
    path = root / f"{first.sha}.json"
    assert path.is_file(), "one JSON file per commit, named <sha>.json"
    json.loads(path.read_text(encoding="utf-8"))

    for name, passed in (("c2", True), ("c3", False), ("pr-17", False)):
        store.save(Snapshot(sha(name), (CaseRecord("bench_t001", "benchmark", passed, 1, False, name),)))
    rerun = Snapshot(sha("c1"), (CaseRecord("bench_t001", "benchmark", True, 2, False, "re-run"),))
    store.save(rerun)
    assert store.load(sha("c1")) == rerun, "saving a commit again replaces its snapshot"

    main = [sha(name) for name in ("c5", "c4", "c3", "c2", "c1")]
    assert store.baseline(main) == store.load(sha("c3")), (
        "the baseline is main's newest commit with results"
    )
    assert store.baseline(main[:2]) is None, "no commit with results, no baseline"
    with pytest.raises(KeyError):
        store.load(sha("c4"))
    for bad in (
        Snapshot("HEAD", first.cases),
        Snapshot(sha("c6")[:7], first.cases),
        Snapshot(sha("c6").upper(), first.cases),
        Snapshot(sha("c6") + "\n", first.cases),
        Snapshot(sha("c6"), (first.cases[0], first.cases[0])),
        Snapshot(sha("c6"), (CaseRecord("online_o009", "Online", True, 1, False, ""),)),
    ):
        with pytest.raises(ValueError):
            store.save(bad)


LIMITS = {"benchmark": 5, "custom": 10, "online": 0}


def rec(cid: str, passed: bool = True, flaky: bool = False) -> CaseRecord:
    category = {"b": "benchmark", "c": "custom", "o": "online"}[cid[0]]
    return CaseRecord(cid, category, passed, 1, flaky, "ok" if passed else "failed")


@pytest.mark.skip("Part 3")
def test_merge_gate(tmp_path) -> None:
    """A pull request is gated case by case against main, one layer at a time."""
    main = Snapshot(sha("c3"), (
        *[rec(f"b{i:02d}", passed=i != 7) for i in range(1, 13)],
        rec("b13", flaky=True),
        rec("b14", flaky=True),
        *[rec(f"c{i:02d}") for i in range(1, 11)],
        rec("c11", flaky=True),
        rec("c12"),
        rec("c13"),
        rec("c99"),
        *[rec(f"o{i}") for i in range(1, 5)],
        rec("b99"),
    ))
    pull = Snapshot(sha("pr-17"), (
        *[rec(f"o{i}", passed=i != 2) for i in range(1, 5)],
        *[rec(f"b{i:02d}", passed=i != 3) for i in range(1, 13)],
        rec("b13", passed=False),
        *[rec(f"c{i:02d}") for i in range(1, 11)],
        rec("c11", passed=False),
        rec("c12", passed=False, flaky=True),
        rec("c13", passed=False, flaky=True),
        *[rec(f"c{i}", passed=False) for i in range(20, 23)],
        *[rec(f"b{i}") for i in range(20, 30)],
        rec("b14"),
    ))
    report = gate(pull, main, LIMITS)
    assert report.regressed == ("o2", "b03"), "a regression is a case that passed on main and fails now"
    assert report.flaky == ("b13", "c11", "c12", "c13", "b14"), (
        "a case flaky here or on main is reported, not counted"
    )
    assert report.new == ("c20", "c21", "c22", *[f"b{i}" for i in range(20, 30)]), (
        "cases main does not have are new, even when they fail"
    )
    assert report.removed == ("c99", "b99"), "cases the pull request dropped are reported"
    assert report.reasons == (
        "benchmark: 1 of 12 comparable cases regressed (limit 5%)",
        "online: 1 of 4 comparable cases regressed (limit 0%)",
    ), "each layer is gated on its own comparable cases"
    assert report.allowed is False, "a blocking reason blocks the merge"

    quiet = Snapshot(sha("c4"), (
        *[rec(f"b{i:02d}") for i in range(1, 41)],
        *[rec(f"o{i}") for i in range(1, 5)],
    ))
    guard = Snapshot(sha("pr-18"), (
        *[rec(f"b{i:02d}") for i in range(1, 41)],
        *[rec(f"o{i}", passed=i != 3) for i in range(1, 5)],
        rec("c50", passed=False),
        rec("c51"),
    ))
    assert gate(guard, quiet, LIMITS) == GateReport(
        False, ("online: 1 of 4 comparable cases regressed (limit 0%)",), regressed=("o3",),
        new=("c50", "c51"),
    ), "one guardrail regression blocks, however many other cases still pass"
    drift = Snapshot(sha("pr-21"), (
        *[rec(f"b{i:02d}", passed=i != 17) for i in range(1, 41)],
        *[rec(f"o{i}") for i in range(1, 5)],
    ))
    assert gate(drift, quiet, LIMITS) == GateReport(True, (), regressed=("b17",)), (
        "a layer may regress up to its limit, and the regression is still reported"
    )
    assert gate(quiet, quiet, LIMITS) == GateReport(True, ()), "an unchanged suite merges"
    assert gate(guard, None, LIMITS) == GateReport(
        False, ("no baseline on main",), new=tuple(case.cid for case in guard.cases)
    ), "without a baseline nothing merges"
    empty = gate(Snapshot(sha("pr-19"), ()), quiet, LIMITS)
    assert (empty.allowed, empty.reasons) == (False, ("no cases",)), "a run with no cases never merges"

    pipeline = EvalPipeline(SnapshotStore(tmp_path / "evals"), LIMITS)
    for name in ("c1", "c2"):
        pipeline.run(sha(name), lesson_suite([]), on_main=True)
    pr_suite = lesson_suite([])
    pr_suite[2] = uncited
    pipeline.run(sha("pr-20"), pr_suite, on_main=False)
    assert pipeline.check(sha("pr-20"), [sha("c2"), sha("c1")]) == GateReport(
        False, ("custom: 1 of 2 comparable cases regressed (limit 10%)",), regressed=("custom_c001",)
    ), "the lesson's suite, through Parts 1-3, blocks a pull request that drops citations"


def unescape(text: str, prop: bool = False) -> str:
    codes = {"%25": "%", "%0D": "\r", "%0A": "\n"}
    if prop:
        codes.update({"%3A": ":", "%2C": ","})
    return re.sub(r"%(?:25|0D|0A|3A|2C)", lambda m: codes.get(m[0], m[0]), text)


def parse_log(text: str) -> list[tuple]:
    """Read the log the way the Actions runner does: a CR, an LF or a CRLF ends a line, and each
    line is one command or one plain log line."""
    assert text.endswith("\n"), "every log line ends in a newline"
    events: list[tuple] = []
    for line in re.split(r"\r\n?|\n", text[:-1]):
        if not line.startswith("::"):
            events.append(("log", line))
            continue
        m = re.fullmatch(r"::([a-z]+)(?: ([^:]*))?::(.*)", line)
        assert m, f"not a workflow command: {line!r}"
        props = {}
        for item in m[2].split(",") if m[2] else []:
            key, sep, value = item.partition("=")
            assert sep, f"a property without a value in {line!r}"
            props[key] = unescape(value, prop=True)
        events.append((m[1], props, unescape(m[3])))
    return events


RECORDS = {
    "bench_t001": CaseRecord("bench_t001", "benchmark", True, 2, False, "FAIL_TO_PASS fixed"),
    "bench_t002": CaseRecord("bench_t002", "benchmark", False, 3, False,
                             "coverage 85% < 90%, see /cov?min=90%25\nmissing sticks: recipe"),
    "custom_c001[en,de]": CaseRecord("custom_c001[en,de]", "custom", True, 1, True, "citations present"),
    "custom_c002": CaseRecord("custom_c002", "custom", False, 1, True,
                              "digest went out without an unsubscribe link"),
    "online:pii-ssn": CaseRecord("online:pii-ssn", "online", False, 1, False,
                                 "ssn was forwarded;\r\nPII guardrail failed"),
}
SUITE = [("bench_t001", "benchmark"), ("custom_c002", "custom"), ("bench_t002", "benchmark"),
         ("online:pii-ssn", "online"), ("custom_c001[en,de]", "custom")]


@pytest.mark.skip("Part 4")
def test_workflow_log() -> None:
    """CI shows one group per layer as soon as it is complete, annotations, then the verdict."""
    finish = ["custom_c002", "bench_t002", "custom_c001[en,de]", "bench_t001", "online:pii-ssn"]
    pulled: list[str] = []
    decided: list[tuple] = []

    async def finished(order):
        for cid in order:
            pulled.append(cid)
            await asyncio.sleep(0)
            yield RECORDS[cid]

    def decide(records):
        decided.append(records)
        return GateReport(False, ("online: 1 of 4 comparable cases regressed (limit 0%)",))

    async def read(suite, order, verdict):
        chunks, group_ends = [], []
        async for chunk in workflow_log(suite, finished(order), verdict):
            chunks.append(chunk)
            group_ends += [len(pulled)] * chunk.count("::endgroup::")
        return "".join(chunks), group_ends

    text, group_ends = asyncio.run(read(SUITE, finish, decide))
    assert parse_log(text) == [
        ("group", {}, "benchmark"),
        ("log", "ok bench_t001 rounds=2"),
        ("error", {"title": "bench_t002"},
         "coverage 85% < 90%, see /cov?min=90%25\nmissing sticks: recipe"),
        ("endgroup", {}, ""),
        ("group", {}, "custom"),
        ("warning", {"title": "custom_c002"}, "digest went out without an unsubscribe link"),
        ("warning", {"title": "custom_c001[en,de]"}, "citations present"),
        ("endgroup", {}, ""),
        ("group", {}, "online"),
        ("error", {"title": "online:pii-ssn"}, "ssn was forwarded;\r\nPII guardrail failed"),
        ("endgroup", {}, ""),
        ("error", {"title": "eval gate"}, "BLOCK\nonline: 1 of 4 comparable cases regressed (limit 0%)"),
    ], "one group per layer, cases in suite order, the verdict last"
    assert decided == [tuple(RECORDS[cid] for cid, _ in SUITE)], (
        "the verdict sees every case, in suite order"
    )
    assert group_ends == [4, 4, 5], (
        "a group goes out as soon as its cases are in and the groups before it are out"
    )

    pulled.clear()
    text, _ = asyncio.run(read(SUITE[3:4] + SUITE[:1], ["bench_t001", "online:pii-ssn"],
                               lambda records: GateReport(True, ())))
    assert [event[0] for event in parse_log(text)] == [
        "group", "log", "endgroup", "group", "error", "endgroup", "notice"
    ], "a layer without cases gets no group"
    assert parse_log(text)[-1] == ("notice", {"title": "eval gate"}, "ALLOW")

    for order in (finish[:4], finish + ["bench_t001"]):
        with pytest.raises(ValueError):
            asyncio.run(read(SUITE, order, decide))


REQUIREMENTS = [
    Requirement("guard:pii", "guardrail"),
    Requirement("rule:verified-cites", "rule", ("rule:scope", "rule:cite")),
    Requirement("rule:cite", "rule"),
    Requirement("guard:budget", "guardrail"),
    Requirement("rule:scope", "rule"),
    Requirement("rule:tests-first", "rule",
                ("rule:scope", "rule:cite", "guard:dom", "rule:verified-cites")),
    Requirement("rule:small-diffs", "rule", ("rule:tests-first", "rule:cite")),
    Requirement("guard:dom", "guardrail"),
]
COVERS = {
    "online_o003": ("guard:pii",),
    "online_o001": ("guard:pii", "rule:scope"),
    "custom_c001": ("rule:cite",),
    "custom_c003": ("rule:cite",),
    "custom_c002": ("rule:verified-cites",),
    "online_o002": ("guard:budget",),
    "bench_t001": ("rule:scope", "rule:tests-first"),
    "bench_t004": ("rule:small-diffs",),
    "online_o004": ("guard:dom",),
}


@pytest.mark.skip("Part 5")
def test_coverage_map() -> None:
    """Every guardrail and learned rule needs a passing case, and so does everything it derives from."""
    run = Snapshot(sha("c7"), (
        CaseRecord("online_o001", "online", True, 1, False, "PII guardrail held"),
        CaseRecord("custom_c001", "custom", True, 1, True, "citations present"),
        CaseRecord("custom_c003", "custom", False, 3, False, "missing citations"),
        CaseRecord("custom_c002", "custom", True, 2, False, "cites retrieved sources"),
        CaseRecord("online_o002", "online", False, 1, False, "over budget"),
        CaseRecord("bench_t001", "benchmark", True, 2, False, "FAIL_TO_PASS fixed"),
        CaseRecord("bench_t004", "benchmark", True, 1, False, "diff under 40 lines"),
        CaseRecord("online_o003", "online", True, 1, False, "PII guardrail held"),
    ))
    report = coverage(REQUIREMENTS, COVERS, run)
    assert list(report.covered.items()) == [
        ("guard:pii", ("online_o001", "online_o003")),
        ("rule:scope", ("online_o001", "bench_t001")),
    ], "covered requirements, in the order given, with the passing non-flaky cases behind them"
    assert list(report.uncovered.items()) == [
        ("rule:verified-cites", ("rule:verified-cites", "rule:cite")),
        ("rule:cite", ("rule:cite",)),
        ("guard:budget", ("guard:budget",)),
        ("rule:tests-first", ("rule:tests-first", "rule:cite")),
        ("rule:small-diffs", ("rule:small-diffs", "rule:tests-first", "rule:cite")),
        ("guard:dom", ("guard:dom",)),
    ], "each uncovered requirement, in the order given, with its chain down to the first gap"

    with pytest.raises(ValueError):
        coverage(REQUIREMENTS, {**COVERS, "custom_c004": ("rule:citations",)}, run)
    for loop in (
        [Requirement("rule:a", "rule", ("rule:b",)), Requirement("rule:b", "rule", ("rule:a",))],
        [Requirement("rule:a", "rule", ("rule:a",))],
        [Requirement("rule:a", "rule", ("rule:zzz",))],
    ):
        with pytest.raises(ValueError):
            coverage(loop, {}, run)
