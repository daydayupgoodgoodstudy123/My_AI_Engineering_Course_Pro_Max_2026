import asyncio
import copy
import csv
import re
import time
from dataclasses import replace

import pytest
from researchops.a2a import DelegationFailed
from researchops.agent import Agent
from researchops.catalog import COLUMNS, Catalog, Paper
from researchops.evidence import assess
from researchops.gateway import AuditEntry, Gateway, Grant
from researchops.job import Budget, run_job
from researchops.protocol import CAPABILITIES_KEY, TASKS, request_meta
from researchops.report import PLACEHOLDER, Summary, stream_report
from researchops.server import ReportPlan, ResearchServer


class FakeTime:
    """A clock that moves only when the agent sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class Recorder:
    """Sits between the gateway and the server and keeps every request that got through."""

    def __init__(self, server: ResearchServer, limit: int = 100) -> None:
        self.server = server
        self.log: list[dict] = []
        self.limit = limit

    def handle(self, request: dict) -> dict:
        self.log.append(copy.deepcopy(request))
        assert len(self.log) <= self.limit, "the agent never stopped sending requests"
        return self.server.handle(request)

    def methods(self) -> list[str]:
        return [request["method"] for request in self.log]

    def tool_calls(self, name: str) -> list[dict]:
        return [r["params"] for r in self.log if r["method"] == "tools/call" and r["params"]["name"] == name]


class FakeWriter:
    """A scripted writer agent. A summary takes 1 + turns[id] event-loop turns and work_s seconds
    of fake time; summaries written side by side overlap in time. Ids in fail fail."""

    def __init__(self, fail: tuple[str, ...] = (), turns: dict[str, int] | None = None, work_s: float = 0.0):
        self.fail = set(fail)
        self.turns = turns or {}
        self.work_s = work_s
        self.time = FakeTime()
        self.calls: list[str] = []
        self.active = 0
        self.peak = 0

    async def send_message(self, paper: dict) -> str:
        self.calls.append(paper["arxiv_id"])
        self.active += 1
        self.peak = max(self.peak, self.active)
        begun = self.time.now
        try:
            for _ in range(1 + self.turns.get(paper["arxiv_id"], 0)):
                await asyncio.sleep(0)
            if paper["arxiv_id"] in self.fail:
                raise DelegationFailed(paper["arxiv_id"])
            return f"Summary of {paper['title']}."
        finally:
            self.active -= 1
            self.time.now = max(self.time.now, begun + self.work_s)


GRANTS = {
    "tok_alice": Grant("alice", frozenset({"research:read", "research:write"})),
    "tok_bob": Grant("bob", frozenset({"research:read"})),
    "tok_carol": Grant("carol", frozenset({"research:write"})),
}


def paper(arxiv_id: str, title: str, year: int = 2026) -> Paper:
    return Paper(arxiv_id, title, ("A. Author",), year, "fixture")


PAPERS = [
    paper("2401.01230", "Agent protocols in practice", 2024),
    paper("2604.01055", "Agent-to-agent coordination benchmarks"),
    paper("2602.20001", "Sparse attention kernels"),
    paper("2603.30016", "Long-running agent tasks"),
    paper("2605.00042", "Agent cards and discovery"),
]
FOUND = ["2401.01230", "2604.01055", "2603.30016", "2605.00042"]


def setup(plan: ReportPlan, *, failing_searches: int = 0, writer: FakeWriter | None = None):
    fake = FakeTime()
    writer = writer or FakeWriter()
    writer.time = fake
    server = Recorder(ResearchServer(PAPERS, plan=plan, failing_searches=failing_searches, clock=fake.clock))
    gateway = Gateway(server, GRANTS)
    agent = Agent(gateway, "tok_alice", writer, sleep=fake.sleep, clock=fake.clock)
    return agent, gateway, server, fake


def tree(spans) -> list[tuple]:
    """(span name, parent span name) for every span, in the order they started."""
    names = {span.span_id: span.name for span in spans}
    return [(span.name, names.get(span.parent_id, "?") if span.parent_id else None) for span in spans]


def tools_call(name: str, arguments: dict, *, tasks: bool = True) -> dict:
    params = {"name": name, "arguments": arguments, "_meta": request_meta(tasks=tasks)}
    return {"method": "tools/call", "params": params}


@pytest.mark.skip("Part 1")
def test_research_run() -> None:
    """One research run: the report comes back as a task, is polled politely, and leaves a correct trace."""
    intervals = [40] * 7 + [80] * 7 + [40] * 6
    agent, gateway, server, fake = setup(ReportPlan(intervals=intervals))
    start = time.perf_counter()
    run = asyncio.run(agent.research("agent"))
    elapsed = time.perf_counter() - start

    assert [hit["arxiv_id"] for hit in run.papers] == FOUND
    assert run.report["content"] == [
        {"type": "text", "text": "Report on 'agent': 4 summaries, 0 missing."},
        {"type": "ui_resource", "uri": "ui://report/tsk_0001"},
    ], "the report's task is followed to its final result"

    spans = agent.tracer.spans
    assert len({span.trace_id for span in spans}) == 1 and all(s.end_ns > s.start_ns for s in spans)
    assert tree(spans) == [
        ("agent.invoke_agent", None),
        ("server/discover", "agent.invoke_agent"),
        ("tools/call arxiv_search", "agent.invoke_agent"),
        *[("a2a.SendMessage", "agent.invoke_agent")] * 4,
        ("tools/call generate_report", "agent.invoke_agent"),
        *[("tasks/get", "tools/call generate_report")] * 20,
    ], "tasks/get polls belong to the tools/call that returned the task"
    sent = [r for r in server.log if r["method"] in ("tools/call", "tasks/get")]
    declared = [TASKS in r["params"]["_meta"][CAPABILITIES_KEY]["extensions"] for r in sent]
    assert len(sent) == 22 and all(declared), (
        "any tools/call may come back as a task, so every one declares the Tasks extension"
    )

    seen = len(server.log)
    report = {"query": "agent", "summaries": []}
    assert gateway.handle("tok_bob", tools_call("generate_report", report)) == {
        "error": "insufficient_scope",
        "scope": "research:write",
    }, "a token needs every scope the tool requires"
    assert gateway.handle("tok_carol", tools_call("generate_report", report)) == {
        "error": "insufficient_scope",
        "scope": "research:read",
    }, "a token needs every scope the tool requires"
    assert len(server.log) == seen, "a refused call never reaches the server"
    assert gateway.audit == [
        AuditEntry("alice", "arxiv_search", "allow"),
        AuditEntry("alice", "generate_report", "allow"),
        AuditEntry("bob", "generate_report", "deny"),
        AuditEntry("carol", "generate_report", "deny"),
    ], "every tools/call decision is audited"
    undeclared = server.server.handle(tools_call("generate_report", report, tasks=False))
    assert undeclared.get("error", {}).get("code") == -32021 and undeclared["error"]["data"] == {
        "requiredCapabilities": {"extensions": {TASKS: {}}}
    }, "a call that may become a task is refused unless it declares the extension"

    assert elapsed < 0.1, "a run should take no wall-clock time when sleep is faked"
    assert fake.slept == pytest.approx([ms / 1000 for ms in intervals]), (
        "wait the server's current pollIntervalMs before each tasks/get"
    )


CATALOG = [
    Paper(
        "2401.01230",
        'Tools, tasks, and "agents":\na field guide',
        ("Lu, Aaron", "Zoë Müller"),
        2024,
        "arxiv-api 2026-10-30",
    ),
    Paper("0912.0410", "Line breaks\r\nfrom a Windows export\rand an old Mac one", ("Smith; J.",), 2009, "fixture"),
    Paper("cs/0112017", "  Padded on purpose  ", (), 2001, "fixture"),
    Paper(
        "2310.06770v2",
        "Versioned ids stay as written",
        ("O'Neil, D.", 'Dana "DJ" Ruiz'),
        2023,
        "arxiv-api 2026-10-30",
    ),
]


@pytest.mark.skip("Part 2")
def test_catalog_roundtrip(tmp_path) -> None:
    """Papers survive a round trip through the CSV catalog, including a reopen and a later append."""
    path = str(tmp_path / "papers.csv")
    catalog = Catalog(path)
    assert catalog.papers() == [], "a catalog whose file does not exist yet is empty"
    for entry in CATALOG[:3]:
        catalog.add(entry)
    assert catalog.papers() == CATALOG[:3], "a paper must round-trip exactly"

    reopened = Catalog(path)
    assert reopened.papers() == CATALOG[:3], "a reopened catalog reads every paper back exactly"
    reopened.add(CATALOG[3])
    with pytest.raises(ValueError):
        reopened.add(replace(CATALOG[0], title="The same id again"))
    papers = Catalog(path).papers()
    assert papers == CATALOG, "appending after a reopen keeps every paper, in the order added"
    assert all(type(entry.year) is int for entry in papers), "the year reads back as an int"

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == list(COLUMNS) and len(rows) == 1 + len(CATALOG), (
        "the file is CSV: one header row, then one row per paper"
    )
    assert [(row[0], row[3]) for row in rows[1:]] == [(p.arxiv_id, str(p.year)) for p in CATALOG], (
        "ids and years are written as plain text"
    )


@pytest.mark.skip("Part 3")
def test_bounded_job() -> None:
    """A job stays inside its budget, survives a failed delegation, and stops polling in time."""
    writer = FakeWriter(fail=("2604.01055",), turns={"2401.01230": 3, "2603.30016": 1})
    agent, gateway, server, fake = setup(ReportPlan(intervals=[250, 250, 500]), failing_searches=1, writer=writer)
    job = asyncio.run(run_job(agent, "agent", Budget(tool_calls=3, delegations=3, wait_ms=10_000)))
    assert job.status == "completed", "a search that answers isError once is retried, and the job completes"
    assert job.papers == FOUND, "papers lists every hit, in search order"
    assert sorted(writer.calls) == sorted(FOUND[:3]) and writer.peak == 3, (
        "the first budget.delegations hits are delegated, all at once"
    )
    assert job.missing == ["2604.01055", "2605.00042"], "a failed or skipped delegation leaves its paper missing"
    assert server.tool_calls("generate_report")[0]["arguments"] == {
        "query": "agent",
        "summaries": [
            {"arxiv_id": "2401.01230", "text": "Summary of Agent protocols in practice."},
            {"arxiv_id": "2603.30016", "text": "Summary of Long-running agent tasks."},
        ],
        "missing": ["2604.01055", "2605.00042"],
    }, "the report gets the summaries in search order, and the missing papers"
    assert job.report["content"][0]["text"] == "Report on 'agent': 2 summaries, 2 missing.", (
        "the report is the completed task's result"
    )
    assert job.tool_calls == 3, "every tools/call counts, the retry included"
    assert job.polls == 3 and fake.slept == pytest.approx([0.25, 0.25, 0.5]), (
        "wait the server's current pollIntervalMs before each poll"
    )
    assert server.methods() == ["server/discover"] + ["tools/call"] * 3 + ["tasks/get"] * 3, (
        "discover, search twice, generate_report, then tasks/get until done: there is no tasks/result"
    )

    for tool_calls in (1, 2):
        agent, gateway, server, fake = setup(ReportPlan(intervals=[250]), failing_searches=1)
        job = asyncio.run(run_job(agent, "agent", Budget(tool_calls=tool_calls, delegations=3, wait_ms=10_000)))
        assert server.methods().count("tools/call") == tool_calls, "a tools/call over budget is never sent"
        assert (job.status, job.tool_calls) == ("over_budget", tool_calls), (
            "the retry counts against the tool-call budget"
        )

    agent, gateway, server, fake = setup(ReportPlan(intervals=[250]), failing_searches=2)
    job = asyncio.run(run_job(agent, "agent", Budget(tool_calls=5, delegations=3, wait_ms=10_000)))
    assert (job.status, job.tool_calls) == ("failed", 2), "a tool that fails again after its one retry fails the job"

    for ttl_ms, wait_ms, polls in ((600, 2_000, 3), (500, 600, 2)):
        never_done = ReportPlan(intervals=[250], finishes=False, ttl_ms=ttl_ms)
        agent, gateway, server, fake = setup(never_done, writer=FakeWriter(work_s=0.5))
        job = asyncio.run(run_job(agent, "agent", Budget(tool_calls=5, delegations=5, wait_ms=wait_ms)))
        assert (job.status, job.polls, job.report) == ("expired", polls, None), (
            f"stop polling once ttlMs have passed since the handle arrived, checked before the wait budget "
            f"(ttlMs {ttl_ms}, budget.wait_ms {wait_ms} here)"
        )

    for wait_ms, polls in ((649, 1), (650, 2), (700, 2)):
        slower = ReportPlan(intervals=[250, 400], finishes=False)
        agent, gateway, server, fake = setup(slower, writer=FakeWriter(work_s=0.5))
        job = asyncio.run(run_job(agent, "agent", Budget(tool_calls=5, delegations=5, wait_ms=wait_ms)))
        waits = [0.25, 0.4][:polls]
        assert (job.status, job.polls) == ("over_budget", polls) and fake.slept == pytest.approx(waits), (
            f"never start a wait that would go past budget.wait_ms ({wait_ms} ms here)"
        )


HEADING = re.compile(r" {0,3}#{1,6}(?:[ \t]|$)")


def sections(text: str) -> list[tuple[str, str]]:
    """(heading line, body) pairs, split where a Markdown renderer sees an ATX heading."""
    found: list[tuple[str, list[str]]] = []
    for line in text.split("\n"):
        if HEADING.match(line):
            found.append((line, []))
        elif found:
            found[-1][1].append(line)
        else:
            assert not line.strip(), f"text before the first heading: {line!r}"
    return [(heading, "\n".join(body).strip("\n")) for heading, body in found]


REPORT_PAPERS = [
    paper("2401.01230", "Tool calls\n  at scale", 2024),
    paper("2604.01055", "Agent-to-agent coordination"),
    paper("2603.30016", "Long-running tool calls via Tasks"),
    paper("2605.00042", "Opaque delegation boundaries"),
    paper("2606.00007", "Trace context across hops"),
]


@pytest.mark.skip("Part 4")
def test_report_stream() -> None:
    """Sections come out in paper order, each one as soon as everything before it is done."""
    third = "Tasks keep long work alive.\n## Methods\n  # indented, still a heading\nC# and F# clients poll."
    arrivals = [
        Summary("2603.30016", third),
        Summary("2604.01055", None),
        Summary("2401.01230", "Fast paths matter."),
        Summary("2606.00007", None),
    ]
    pulled: list[str] = []

    async def arriving():
        for summary in arrivals:
            pulled.append(summary.arxiv_id)
            yield summary

    async def drain() -> list[tuple[str, int]]:
        return [(chunk, len(pulled)) async for chunk in stream_report(REPORT_PAPERS, arriving())]

    emitted = asyncio.run(drain())
    text = "".join(chunk for chunk, _ in emitted)
    assert sections(text) == [
        (
            "## Search results",
            "- 2401.01230 (2024): Tool calls at scale\n"
            "- 2604.01055 (2026): Agent-to-agent coordination\n"
            "- 2603.30016 (2026): Long-running tool calls via Tasks\n"
            "- 2605.00042 (2026): Opaque delegation boundaries\n"
            "- 2606.00007 (2026): Trace context across hops",
        ),
        ("## 2401.01230: Tool calls at scale", "Fast paths matter."),
        ("## 2604.01055: Agent-to-agent coordination", PLACEHOLDER),
        (
            "## 2603.30016: Long-running tool calls via Tasks",
            "Tasks keep long work alive.\n\\## Methods\n  \\# indented, still a heading\nC# and F# clients poll.",
        ),
        ("## 2605.00042: Opaque delegation boundaries", PLACEHOLDER),
        ("## 2606.00007: Trace context across hops", PLACEHOLDER),
        ("## Conclusion", "Summarized 2 of 5 papers. Missing: 2604.01055, 2605.00042, 2606.00007."),
    ], "sections in paper order, and a summary never opens a section of its own"

    went_out: dict[str, int] = {}
    so_far = ""
    for chunk, pulls in emitted:
        so_far += chunk
        for heading, _ in sections(so_far[: so_far.rfind("\n") + 1]):
            went_out.setdefault(heading, pulls)
    assert list(went_out.values()) == [0, 3, 3, 3, 4, 4, 4], (
        "a section goes out as soon as it and every section before it are complete"
    )


def span(trace_id: str, span_id: str, parent: str | None) -> dict:
    return {"traceId": trace_id, "spanId": span_id, "parentSpanId": parent}


TREE = [span("t1", "a", None), span("t1", "b", "a"), span("t1", "c", "b"), span("t1", "d", "a")]
CLAIMS = {
    "the report survives a restart": ["tasks"],
    "every hop is traced": ["telemetry"],
    "summaries come from the writer agent": ["delegation", "every hop is traced"],
    "the research run is production ready": [
        "summaries come from the writer agent",
        "the report survives a restart",
        "every hop is traced",
        "delegation",
        "authorization",
        "sandbox",
    ],
}
ALL_TASK_TESTS = ["state-transition tests", "input tests", "cancellation tests", "recovery tests"]


@pytest.mark.skip("Part 5")
def test_evidence_claims() -> None:
    """A claim is proven only when every boundary under it was crossed for real, with its evidence."""
    run = {
        "tasks": {"mode": "real", "evidence": ALL_TASK_TESTS + ["unit tests"]},
        "delegation": {"mode": "real", "evidence": ["contract tests", "retry tests", "timeout tests"]},
        "telemetry": {"mode": "real", "received": TREE[:3] + [span("t1", "d", "x")]},
        "authorization": {"mode": "simulated", "evidence": ["allow audit cases", "deny audit cases"]},
    }
    result = assess(CLAIMS, run)
    assert list(result) == list(CLAIMS), "claims come back in the order given"
    assert result["the report survives a restart"] == [], "a real boundary with all its evidence proves its claim"
    assert result["every hop is traced"] == ["telemetry: trace-parent assertions"], (
        "parentage is judged from the spans the collector received; a shared trace id alone does not prove it"
    )
    assert result["summaries come from the writer agent"] == [
        "delegation: opacity tests",
        "telemetry: trace-parent assertions",
    ], "a claim lacks what the claims under it lack"
    assert result["the research run is production ready"] == [
        "authorization: allow audit cases",
        "authorization: deny audit cases",
        "delegation: opacity tests",
        "telemetry: trace-parent assertions",
        "sandbox: escape tests",
        "sandbox: egress tests",
        "sandbox: secret tests",
        "sandbox: resource-limit tests",
    ], "missing evidence is listed once, in BOUNDARIES order, and a simulation proves nothing"

    def traced(received: list[dict]) -> list[str]:
        telemetry = {"telemetry": {"mode": "real", "received": received}}
        return assess({"every hop is traced": ["telemetry"]}, telemetry)["every hop is traced"]

    assert traced(TREE) == [], "spans that form one tree prove parentage"
    assert traced(TREE + [span("t1", "e", None)]) == ["telemetry: trace-parent assertions"], (
        "one trace has one root"
    )
    assert traced(TREE + [span("t2", "e", "c")]) == ["telemetry: trace-parent assertions"], (
        "every span of the run carries the same trace id"
    )
    assert traced([]) == ["telemetry: collector receipt", "telemetry: trace-parent assertions"], (
        "a collector that received nothing proves nothing"
    )
    simulated = {"telemetry": {"mode": "simulated", "received": TREE}}
    assert assess({"every hop is traced": ["telemetry"]}, simulated)["every hop is traced"] == [
        "telemetry: collector receipt",
        "telemetry: trace-parent assertions",
    ], "a simulated collector proves nothing, whatever spans it lists"

    with pytest.raises(ValueError):
        assess({"billing is audited": ["billing"]}, {})
    with pytest.raises(ValueError):
        assess({"the report survives a restart": ["tasks"]}, {"billing": {"mode": "real", "evidence": []}})
    with pytest.raises(ValueError):
        assess({"a": ["tasks", "b"], "b": ["c"], "c": ["a"]}, {})
