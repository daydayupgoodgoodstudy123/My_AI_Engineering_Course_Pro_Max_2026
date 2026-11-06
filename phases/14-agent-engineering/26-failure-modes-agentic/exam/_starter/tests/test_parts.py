import asyncio
import os
import re
import time

import pytest
from failtag.cascade import Cascade, cascade_report
from failtag.detectors import parse_constraint, tag
from failtag.drift import Alert, DriftMonitor, build_gate, mode_rates
from failtag.online import MESSAGES, End, Start, Step, tag_online
from failtag.service import FailTagService
from failtag.store import TraceStore
from failtag.trace import Trace, TraceStep


def call(name: str, args: dict | None = None, status: str = "ok") -> TraceStep:
    return TraceStep("tool_call", name, args or {}, status)


def trace(request: str, steps: list, constraints=(), claim=True, changed=True, tid="t") -> Trace:
    return Trace(tid, request, list(constraints), list(steps), claim, changed)


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def replay(events: list):
    for event in events:
        yield event


def lesson_traces() -> list[Trace]:
    """The lesson's synthetic traces; t004's later calls use the failed search's result."""
    return [
        trace("find the config file", [call("search", {"query": "config"}),
              call("read_file", {"path": "config.yml"})], ["do not modify any files"],
              changed=False, tid="t001"),
        trace("find the config file", [call("search", {"query": "config"}),
              call("write_file", {"path": "config.yml", "content": "..."})],
              ["do not modify any files"], tid="t002"),
        trace("list project files", [call("magic_scanner", {"path": "/"})], changed=False, tid="t003"),
        trace("look up invoice 4711", [call("search", {"query": "invoice 4711"}, status="error"),
              call("read_file", {"path": "${0}"}),
              call("write_file", {"path": "${0}", "content": "fabricated"}),
              call("list_dir", {"path": "/tmp"})], tid="t004"),
        trace("update readme with release notes", [call("read_file", {"path": "README.md"}),
              call("write_file", {"path": "README.md", "content": "notes"}),
              call("write_file", {"path": "src/foo.py", "content": "also notes"})],
              ["do not modify src/"], tid="t005"),
        trace("read some file", [call("read_file", {"file": "/tmp/foo"})], claim=False,
              changed=False, tid="t006"),
        trace("create a PR", [call("search", {"query": "PR template"})], changed=False, tid="t007"),
    ]


@pytest.mark.skip("Part 1")
def test_detectors() -> None:
    """Each detector does what its docstring says, and stays fast on long traces."""
    assert tag(trace("list project files", [call("magic_scanner", {"path": "/"})],
                     changed=False)) == ["hallucinated_action"]

    memo = trace("summarize the credit memo", [call("read_file", {"path": "memo.txt"}),
                 call("write_file", {"path": "summary.txt", "content": "..."})])
    assert tag(memo) == ["scope_creep"], "a write verb only counts as a whole word of the request"
    saved = trace("list the saved searches", [call("write_file", {"path": "saved.txt", "content": "..."})])
    assert tag(saved) == ["scope_creep"], "a write verb only counts as a whole word of the request"
    for request in ("Edit the README.", "Fix the typo, then SAVE."):
        assert tag(trace(request, [call("write_file", {"path": "README.md", "content": "x"})])) == [], (
            "write verbs count whatever their case or punctuation"
        )

    rules = ["do not exceed 5 searches", "Do not modify src/"]
    docs = [call("write_file", {"path": "docs/a.md", "content": "x"})]
    assert tag(trace("update the docs", docs, rules)) == [], "a rule on a path/ only covers that path"
    assert parse_constraint(rules[0]) is None, "a verb missing from VERB_TOOLS makes no tool rule"
    src = [call("read_file", {"path": "src/a.py"}), call("write_file", {"path": "src/a.py", "content": "x"})]
    assert tag(trace("update the docs", src, rules)) == ["context_loss"], (
        "a do-not constraint forbids the tools its verb names"
    )
    assert tag(trace("update the docs", docs, ["do not modify any files"])) == ["context_loss"]

    independent = [call("search", {"query": "invoice 4711"}, status="error"),
                   call("list_dir", {"path": "/invoices"}),
                   call("read_file", {"path": "${1}"}),
                   call("read_file", {"path": "${1}/index.txt"})]
    assert tag(trace("look up invoice 4711", independent)) == [], (
        "only calls that use the failed result are downstream of it"
    )
    split = [call("search", {"query": "invoice 4711"}, status="error"),
             call("search", {"query": "invoice 4712"}, status="error"),
             call("read_file", {"path": "${0}"}),
             call("read_file", {"path": "${1}"}),
             TraceStep("message", "final", {"text": "Could not open ${0} or ${1}"})]
    assert tag(trace("look up both invoices", split)) == [], (
        "a failure cascades only when two later tool calls use its own result"
    )
    twice = [call("search", {"query": "invoice 4711"}, status="error"),
             call("read_file", {"path": "${0}", "fallback": "${0}.bak"}),
             call("list_dir", {"path": "/invoices"})]
    assert tag(trace("look up invoice 4711", twice)) == [], (
        "a call that uses the failed result twice is one consumer"
    )
    nested = [call("search", {"query": "invoice 4711"}, status="error"),
              call("list_dir", {"path": "/invoices"}),
              call("read_file", {"path": "${0}"}),
              call("search", {"query": "retry", "filters": {"ids": ["${1}", "${0}"]}})]
    assert tag(trace("look up invoice 4711", nested)) == ["cascading_errors"], (
        "a failed result used by two later calls cascades"
    )

    n = 4000
    long_steps = [call("search", {"query": f"q{i}", "filters": {"page": i}},
                       status="error" if i % 2 == 0 else "ok") for i in range(n)]
    long_steps[2001] = call("read_file", {"path": "${2000}"})
    long_steps[3999] = call("search", {"query": "retry ${2000}"})
    long_trace = trace("look up the logs", long_steps)
    start = time.perf_counter()
    labels = tag(long_trace)
    elapsed = time.perf_counter() - start
    assert labels == ["cascading_errors"], "a failed result used far downstream still cascades"
    assert elapsed < 0.12, "tagging should be fast on long traces"


@pytest.mark.skip("Part 2")
def test_trace_store(tmp_path, monkeypatch) -> None:
    """Labeled traces and the baseline survive a reopen exactly, and the baseline updates atomically."""
    root = tmp_path / "store"
    tricky = Trace(
        "run/7\n",
        "Order SKU \"A-17\" ] — café",
        ["do not modify src/"],
        [
            call("search", {"query": "sku A-17", "filters": {"tags": ["x", "y"], "limit": 3,
                 "price": 0.1 + 0.2, "deep": [{"k": None, "big": 12345678901234567890}]}},
                 status="error"),
            TraceStep("message", "final", {}, "ok", "404 Not Found\n\tno such SKU ✓"),
        ],
        True,
        False,
    )
    lower = trace("find the config file", [call("search", {"query": "config"})], tid="t001")
    upper = trace("Find the config file", [call("write_file", {"path": "c", "content": ""})], tid="T001")

    store = TraceStore(str(root))
    store.put(tricky, ["tool_misuse", "context_loss"])
    store.put(lower, [])
    store.put(upper, ["scope_creep"])
    assert store.get("run/7\n") == (tricky, ["tool_misuse", "context_loss"]), (
        "a stored trace round-trips exactly"
    )
    assert store.get("t001") == (lower, []) and store.get("T001") == (upper, ["scope_creep"]), (
        "trace ids are case-sensitive"
    )
    with pytest.raises(KeyError):
        store.get("t002")
    store.put(lower, ["context_loss"])

    reopened = TraceStore(str(root))
    assert reopened.tids() == ["T001", "run/7\n", "t001"], "a reopened store lists every trace once, sorted"
    assert reopened.get("t001") == (lower, ["context_loss"]), "putting a trace again replaces it"
    assert reopened.baseline() is None, "there is no baseline until one is set"
    with pytest.raises(ValueError):
        reopened.set_baseline(["t001", "t002"])
    assert reopened.baseline() is None, "a rejected baseline is not stored"
    reopened.set_baseline(["t001", "run/7\n"])
    assert TraceStore(str(root)).baseline() == ["t001", "run/7\n"], "the baseline survives a reopen, in order"
    files = sorted(p for p in root.rglob("*") if p.is_file())
    assert len(files) == 4, "one file per trace, plus the baseline"

    def refuse(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    monkeypatch.setattr(os, "rename", refuse)
    try:
        reopened.set_baseline(["T001"])
    except OSError:
        pass
    else:
        pytest.fail("the baseline is replaced in one atomic step")
    monkeypatch.undo()
    assert TraceStore(str(root)).baseline() == ["t001", "run/7\n"], "a failed update keeps the old baseline"
    assert sorted(p for p in root.rglob("*") if p.is_file()) == files, "no temporary files are left behind"


def fill(store: TraceStore, prefix: str, n: int, labels_of) -> list[str]:
    tids = []
    for i in range(n):
        tid = f"{prefix}-{i:03d}"
        store.put(trace("find the logs", [call("search", {"query": tid})], tid=tid), labels_of(i))
        tids.append(tid)
    return tids


@pytest.mark.skip("Part 3")
def test_drift_and_gate(tmp_path) -> None:
    """Rates are compared with the frozen last-known-good baseline; pages are rate-limited per mode."""
    assert mode_rates([["scope_creep"], [], [], ["scope_creep", "tool_misuse"]]) == {
        "scope_creep": 0.5,
        "tool_misuse": 0.25,
    }, "clean traces count in the denominator"
    assert mode_rates([["tool_misuse", "tool_misuse"], []]) == {"tool_misuse": 0.5}, (
        "a trace counts once per mode"
    )
    assert build_gate([["tool_misuse"]] + [[]] * 19) == ["tool_misuse"], "a mode on exactly 5% fails the build"
    assert build_gate([["tool_misuse"]] + [[]] * 20) == [], "a mode under 5% passes"
    assert build_gate([["context_loss"]] * 14 + [[]] * 186, threshold=0.07) == ["context_loss"], (
        "a mode on exactly the threshold fails the build"
    )
    assert build_gate([]) == []

    now = [1000.0]
    store = TraceStore(str(tmp_path / "drift"))
    monitor = DriftMonitor(store, lambda: now[0], tolerance=0.05, min_traces=20, cooldown_s=600.0)
    good = fill(store, "good", 25, lambda i: ["context_loss"] if i < 10 else ["scope_creep"] if i < 11 else [])
    with pytest.raises(LookupError):
        monitor.check(good)
    monitor.confirm(good)

    a = fill(store, "a", 25, lambda i: ["context_loss"] if i < 10 else ["scope_creep"] if i < 12 else [])
    assert monitor.check(a) == [], "4% above the baseline is within tolerance"
    b = fill(store, "b", 25, lambda i: ["context_loss"] if i < 10 else ["scope_creep"] if i < 13 else [])
    assert monitor.check(b) == [Alert("scope_creep", 1 / 25, 3 / 25)], (
        "drift is measured against the last-known-good baseline"
    )
    now[0] = 1300.0
    assert monitor.check(b) == [], "a mode pages at most once per cooldown"
    c = fill(store, "c", 25, lambda i: ["context_loss"] if i < 10 else ["tool_misuse"] if i < 13 else [])
    assert monitor.check(b + c) == [Alert("tool_misuse", 0.0, 3 / 50)], "each mode has its own cooldown"
    now[0] = 1700.0
    assert monitor.check(b) == [Alert("scope_creep", 1 / 25, 3 / 25)], (
        "a suppressed alert does not restart the cooldown"
    )
    now[0] = 2000.0
    assert monitor.check(b) == [], "the cooldown counts from the latest page"
    now[0] = 2300.0
    assert monitor.check(b) == [Alert("scope_creep", 1 / 25, 3 / 25)], (
        "a mode pages again once cooldown_s has passed"
    )
    calm = fill(store, "calm", 25, lambda i: [])
    assert monitor.check(calm) == [], "falling rates are not drift"
    f = fill(store, "f", 25, lambda i: ["tool_misuse"] if i < 3 else ["context_loss"] if i < 15 else [])
    assert monitor.check(f) == [Alert("context_loss", 10 / 25, 12 / 25), Alert("tool_misuse", 0.0, 3 / 25)], (
        "alerts come sorted by mode"
    )
    assert store.baseline() == good, "only confirm() moves the baseline"

    fresh = DriftMonitor(store, lambda: now[0], min_traces=20)
    d = fill(store, "d", 20, lambda i: ["context_loss"] if i < 8 else ["scope_creep"] if i < 11 else [])
    assert fresh.check(d[:19]) == [], "fewer than min_traces traces give no verdict"
    assert fresh.check(d) == [Alert("scope_creep", 1 / 25, 3 / 20)], (
        "a window of exactly min_traces traces gets a verdict"
    )
    e = fill(store, "e", 20, lambda i: ["tool_misuse"] if i == 0 else [])
    assert fresh.check(e) == [], "a mode exactly tolerance above its baseline has not drifted"

    service = FailTagService(str(tmp_path / "service"), clock=lambda: now[0], min_traces=7)
    labels = {t.tid: service.ingest(t) for t in lesson_traces()}
    assert labels == {
        "t001": [],
        "t002": ["scope_creep", "context_loss"],
        "t003": ["hallucinated_action"],
        "t004": ["scope_creep", "cascading_errors"],
        "t005": ["context_loss"],
        "t006": ["tool_misuse"],
        "t007": ["success_hallucination"],
    }, "tag the lesson's traces end to end"
    assert service.gate(list(labels)) == sorted(set(sum(labels.values(), []))), "every mode here is over 5%"
    service.monitor.confirm(list(labels))
    later = []
    for i in range(7):
        copy = trace("find the config file", [call("write_file", {"path": "config.yml", "content": "x"})],
                     ["do not modify any files"], tid=f"late-{i}")
        service.ingest(copy)
        later.append(copy.tid)
    assert service.watch(later) == [
        Alert("context_loss", 2 / 7, 1.0),
        Alert("scope_creep", 2 / 7, 1.0),
    ], "tag, store and compare end to end"


T0 = 1793608200.0  # 2026-11-02T08:30:00Z

RECORD = re.compile(
    r'<(\d+)>1 (\S+) (\S+) (\S+) (\S+) (\S+) \[failtag@32473((?: [a-z]+="(?:[^"\\\]]|\\.)*")*)\] (.+)'
)
PARAM = re.compile(r' ([a-z]+)="((?:[^"\\\]]|\\.)*)"')


def unescape(value: str) -> str:
    out, i = [], 0
    while i < len(value):
        if value[i] == "\\":
            assert value[i + 1] in '"\\]', "only \", \\ and ] are escaped in param values"
            out.append(value[i + 1])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def parse_syslog(text: str) -> list[tuple]:
    assert text.endswith("\n"), "every record ends with a newline"
    records = []
    for line in text[:-1].split("\n"):
        m = RECORD.fullmatch(line)
        assert m, f"every line is an RFC 5424 record: {line!r}"
        params = {name: unescape(value) for name, value in PARAM.findall(m.group(7))}
        records.append((int(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6),
                        params, m.group(8)))
    return records


@pytest.mark.skip("Part 4")
def test_online_syslog() -> None:
    """Interleaved traces are tagged independently; each mode is reported once per trace, as syslog."""
    odd = 'b"]\\'
    now = [T0]
    script = [
        (0.0, Start("a", "find the config file", ["do not modify any files"])),
        (0.0, Start(odd, "make a README", [])),
        (0.25, Step("a", call("search", {"query": "config"}))),
        (0.5, Step(odd, call('magic"scan]', {"path": "/"}))),
        (1.0, Step("a", call("write_file", {"path": "config.yml", "content": "x"}))),
        (1.25, Start("c", "list project files", [])),
        (1.5, Step(odd, call("search", {"query": "readme"}, status="error"))),
        (1.75, Step(odd, call("read_file", {"path": "${1}"}))),
        (2.0, Step("a", call("write_file", {"path": "${1}"}))),
        (2.25, Step(odd, call("list_dir", {"path": "${1}", "also": ["${1}", "${2}"]}))),
        (2.5, Step("c", call("write_file", {"path": "files.txt", "content": "..."}))),
        (2.75, End("a", True, True)),
        (3.0, End(odd, True, False)),
        (3.25, End("c", False, False)),
    ]

    async def feed():
        for offset, event in script:
            now[0] = T0 + offset
            yield event

    lines = collect(tag_online(feed(), lambda: now[0], host="agent-1"))
    records = parse_syslog("".join(lines))
    found = [(r[6]["tid"], r[5]) for r in records]
    assert len(found) == len(set(found)), "each mode is reported once per trace"
    assert [r[5] for r in records] == [
        "hallucinated_action", "scope_creep", "context_loss", "tool_misuse", "cascading_errors",
        "scope_creep", "success_hallucination",
    ], "traces are tagged independently, each finding when its event arrives"
    assert [r[6] for r in records] == [
        {"tid": odd, "step": "0", "tool": 'magic"scan]'},
        {"tid": "a", "step": "1", "tool": "write_file"},
        {"tid": "a", "step": "1", "tool": "write_file"},
        {"tid": "a", "step": "2", "tool": "write_file"},
        {"tid": odd, "step": "3", "tool": "list_dir"},
        {"tid": "c", "step": "0", "tool": "write_file"},
        {"tid": odd},
    ], "structured data values round-trip"
    assert [r[0] for r in records] == [131, 132, 131, 132, 130, 132, 131], (
        "PRI is FACILITY * 8 + SEVERITY[mode]"
    )
    assert [r[1] for r in records] == [
        "2026-11-02T08:30:00.500Z", "2026-11-02T08:30:01.000Z", "2026-11-02T08:30:01.000Z",
        "2026-11-02T08:30:02.000Z", "2026-11-02T08:30:02.250Z", "2026-11-02T08:30:02.500Z",
        "2026-11-02T08:30:03.000Z",
    ], "TIMESTAMP is the clock in UTC, with milliseconds"
    assert {r[2:5] for r in records} == {("agent-1", "failtag", "-")}, "HOST, then failtag and a - for PROCID"
    assert [r[7] for r in records] == [MESSAGES[r[5]] for r in records], "MESSAGE is MESSAGES[mode]"

    quiet = [
        Start("q", "look up both invoices", []),
        Step("q", call("search", {"query": "invoice 4711"}, status="error")),
        Step("q", call("search", {"query": "invoice 4712"}, status="error")),
        Step("q", call("read_file", {"path": "${0}"})),
        Step("q", call("read_file", {"path": "${1}"})),
        Step("q", TraceStep("message", "final", {"text": "Could not open ${0} or ${1}"})),
        End("q", False, False),
    ]
    assert collect(tag_online(replay(quiet), lambda: T0)) == [], (
        "a failure cascades only when two later tool calls use its own result"
    )

    pulled: list[int] = []

    async def probe():
        yield Start("p", "find the logs", [])
        pulled.append(0)
        yield Step("p", call("teleport", {"to": "prod"}))
        for i in range(100):
            pulled.append(i + 1)
            yield Step("p", call("search", {"query": "logs"}))
        yield End("p", False, False)

    async def first_line() -> str:
        agen = tag_online(probe(), lambda: T0)
        line = await agen.__anext__()
        await agen.aclose()
        return line

    assert parse_syslog(asyncio.run(first_line()))[0][5] == "hallucinated_action"
    assert len(pulled) <= 1, "report a finding as soon as its step arrives"


@pytest.mark.skip("Part 5")
def test_cascade_radius() -> None:
    """Each root-cause failure gets the radius, depth and systems of what it broke downstream."""
    phantom = trace("order SKU 9981", [
        call("catalog.lookup", {"sku": "9981"}, status="error"),
        call("inventory.reserve", {"item": "${0}"}),
        call("billing.charge", {"order": {"item": "${0}", "hold": "${1}"}}, status="error"),
        call("shipping.create", {"lines": [{"hold": "${1}"}, {"charge": "${2}"}]}),
        call("email.send", {"to": "buyer", "body": "Shipped ${3}"}, status="error"),
        call("crm.note", {"text": "customer called"}),
        TraceStep("message", "final", {"text": "Order ${3} placed"}),
    ])
    report = cascade_report(phantom)
    assert [c.step for c in report] == [0], "a failure caused by an earlier failure is not a root cause"
    assert report[0].radius == 5, "each affected step counts once, messages included"
    assert report[0].depth == 4, "depth follows the longest chain of affected steps"
    assert report[0].systems == ["billing", "email", "inventory", "shipping"], (
        "systems come from the affected tool calls"
    )

    two = trace("notify the customer", [
        call("catalog.lookup", {"sku": "1"}, status="error"),
        call("crm.lookup", {"id": "7"}, status="error"),
        call("inventory.reserve", {"item": "${0}"}),
        call("email.send", {"to": "${1}", "body": "${2}"}),
        call("audit.log", {"entry": "${3}"}),
    ])
    assert cascade_report(two) == [
        Cascade(0, 3, 3, ["audit", "email", "inventory"]),
        Cascade(1, 2, 2, ["audit", "email"]),
    ], "a step affected by two root causes counts for both"
    assert cascade_report(trace("find the logs", [call("search", {"query": "logs"})])) == []
    relay = trace("refund order 12", [
        call("search", {"query": "order 12"}, status="error"),
        call("orders.get", {"id": "12"}, status="error"),
        call("payments.refund", {"order": "${1}"}, status="error"),
        call("email.send", {"body": "Refunded ${2}"}),
    ])
    assert cascade_report(relay) == [Cascade(0, 0, 0, []), Cascade(1, 2, 2, ["email", "payments"])], (
        "a failure nothing used is still a root cause, and a cascade runs on through the failures it causes"
    )

    malformed = [
        [call("a.read", {"q": "${1}"}), call("b.write", {})],
        [call("a.read", {"q": "${0}"})],
        [call("a.read", {}), call("b.write", {"q": "${9}"})],
    ]
    for steps in malformed:
        with pytest.raises(ValueError):
            cascade_report(trace("x", steps))

    chain = [call("queue.pop", {}, status="error")]
    chain += [call(f"svc{i % 3}.step", {"prev": "${%d}" % i}) for i in range(2999)]
    assert cascade_report(trace("drain the queue", chain)) == [
        Cascade(0, 2999, 2999, ["svc0", "svc1", "svc2"])
    ], "a long chain must not overflow the stack"
