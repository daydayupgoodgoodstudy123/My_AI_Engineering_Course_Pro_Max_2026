import asyncio
import json
import time

import pytest
from tracejudge.annotations import Annotation, AnnotationQueue
from tracejudge.clusters import Cluster, cluster_traces, signature
from tracejudge.ingest import ingest_stream
from tracejudge.regress import Bisection, bisect_versions
from tracejudge.spans import Span, TraceCollector, load_spans
from tracejudge.summary import SessionSummary, summarize


def exported(trace, span, session, name, parent=None, status="ok", **attributes) -> str:
    """One line as the exporter writes it."""
    return json.dumps({
        "trace_id": trace, "span_id": span, "session_id": session, "name": name,
        "parent_id": parent, "status": status, "attributes": attributes,
    })


REF = "gen_ai.output.reference_id"
EXPORT = [
    # sess-a: two traces; every trace has two chat spans
    exported("a1", "a1-1", "sess-a", "invoke_agent"),
    exported("a1", "a1-2", "sess-a", "chat", "a1-1", tokens="700", **{REF: "c1"}),
    exported("a1", "a1-3", "sess-a", "tool_call search_tool", "a1-1", **{"gen_ai.tool.name": "search_tool"}),
    exported("a1", "a1-4", "sess-a", "chat", "a1-1", tokens=300, **{REF: "c2"}),
    exported("a2", "a2-1", "sess-a", "invoke_agent"),
    exported("a2", "a2-2", "sess-a", "chat", "a2-1", "error", tokens=0, **{"error.reason": "rate_limited"}),
    exported("a2", "a2-3", "sess-a", "chat", "a2-1", tokens="2500", **{REF: "c3"}),
    # sess-b: the exporter numbers spans 1, 2, 3 inside every trace
    exported("b1", "1", "sess-b", "invoke_agent"),
    exported("b1", "2", "sess-b", "chat", "1", tokens="1200", **{REF: "c4"}),
    exported("b1", "3", "sess-b", "tool_call search_tool", "1"),
    exported("b2", "1", "sess-b", "invoke_agent"),
    exported("b2", "2", "sess-b", "chat", "1", tokens=400, **{REF: "c5"}),
    exported("b2", "3", "sess-b", "tool_call web_fetch", "1", "error", **{"error.reason": "tool_timeout"}),
    # sess-c: the exporter retried one span after a timeout
    exported("c1", "c1-1", "sess-c", "invoke_agent"),
    exported("c1", "c1-2", "sess-c", "chat", "c1-1", "error", tokens="900", **{"error.reason": "guardrail_tripped"}),
    exported("c1", "c1-2", "sess-c", "chat", "c1-1", "error", tokens="900", **{"error.reason": "guardrail_tripped"}),
    exported("c1", "c1-3", "sess-c", "chat", "c1-1", tokens=100, **{REF: "c6"}),
    "",
]


@pytest.mark.skip("Part 1")
def test_session_dashboard() -> None:
    """Exported spans become one dashboard row per session, judged trace by trace."""
    collector = TraceCollector()
    stored = [collector.ingest(span) for span in load_spans(EXPORT)]
    summaries = summarize(collector)
    by = {s.session_id: s for s in summaries}

    assert by["sess-a"].span_count == 7, "spans that share a name are still separate spans"
    assert by["sess-b"].span_count == 6, "span ids are unique within a trace, not across traces"
    assert stored.count(False) == 1, "a span the exporter sent twice is stored once"
    assert (by["sess-c"].span_count, by["sess-c"].error_count, by["sess-c"].tokens) == (3, 1, 1000), (
        "a retried span is counted once"
    )
    assert by["sess-a"].tokens == 3500 and isinstance(by["sess-a"].tokens, int), "tokens add up as ints"
    assert all(isinstance(s.attributes.get("tokens", 0), int) for s in load_spans(EXPORT)), (
        "load_spans returns tokens as ints"
    )
    assert [by[s].trace_count for s in ("sess-a", "sess-b", "sess-c")] == [2, 2, 1], (
        "trace_count counts traces, not spans"
    )
    assert [by[s].eval_score_mean for s in ("sess-a", "sess-b", "sess-c")] == pytest.approx([0.7, 0.8, 0.5]), (
        "judge each trace on its own spans, then average over the session"
    )
    assert [s.session_id for s in summaries] == ["sess-c", "sess-a", "sess-b"], "worst sessions first"
    assert by["sess-b"] == SessionSummary("sess-b", 2, 6, 1, 1600, pytest.approx(0.8), {"tool_timeout": 1})

    resent = [Span(f"t{i // 4}", str(i % 4), f"s{i // 40}", "chat") for i in range(8000)]
    again = TraceCollector()
    start = time.perf_counter()
    kept = [again.ingest(span) for span in resent + resent]
    elapsed = time.perf_counter() - start
    assert kept.count(True) == 8000, "a resent batch is stored once"
    assert elapsed < 0.05, "ingest must stay fast when an exporter resends a whole batch"

    many = [Span(f"t{i}", "1", f"s{i:05d}", "chat", attributes={"tokens": i % 2000, REF: f"r{i}"}) for i in range(5000)]
    big = TraceCollector()
    start = time.perf_counter()
    for span in many:
        big.ingest(span)
    rows = summarize(big)
    elapsed = time.perf_counter() - start
    assert len(rows) == 5000 and rows[0].session_id == "s00000"
    assert elapsed < 0.15, "ingest and summarize must stay fast with many sessions"


@pytest.mark.skip("Part 2")
def test_annotation_queue(tmp_path) -> None:
    """Human annotations survive a reopen exactly, and the queue keeps its order."""
    path = str(tmp_path / "review.sqlite3")
    queue = AnnotationQueue(path)
    for trace_id in ("tr-9", "tr-10", "tr-2", "tr-31"):
        queue.enqueue(trace_id)
    queue.enqueue("tr-9")
    assert queue.pending() == ["tr-9", "tr-10", "tr-2", "tr-31"], "pending traces keep their queue order"

    made = [
        queue.annotate("tr-10", "maya", "hallucination", 0.0,
                       "Cites a paper\nthat does not exist.\n", 1767225600123456789),
        queue.annotate("tr-10", "li", "needs_review", None, "", 1767225600123456001),
        queue.annotate("tr-2", "maya", "partial", 1 / 3, "  first pass", 1767225600999999999),
        queue.annotate("tr-2", "maya", "correct", 0.1 + 0.2, "second look\r\n", 1767225601000000003),
    ]
    assert made[0] == Annotation("tr-10", "maya", "hallucination", 0.0,
                                 "Cites a paper\nthat does not exist.\n", 1767225600123456789)
    queue.close()

    reopened = AnnotationQueue(path)
    assert [a.annotator for a in reopened.annotations("tr-10")] == ["maya", "li"], (
        "annotations come back in the order they were made, whatever the annotators' clocks say"
    )
    assert reopened.annotations("tr-10") + reopened.annotations("tr-2") == made, (
        "a reopened queue gives back every annotation exactly"
    )
    assert reopened.annotations("tr-9") == []
    reopened.enqueue("tr-2")
    assert reopened.pending() == ["tr-9", "tr-31"], "pending traces keep their queue order"
    with pytest.raises(KeyError):
        reopened.annotate("tr-404", "maya", "correct", 1.0, "", 1767225602000000000)
    for bad in (1.5, -0.1, float("nan")):
        with pytest.raises(ValueError):
            reopened.annotate("tr-9", "maya", "correct", bad, "", 1767225602000000000)
    assert reopened.pending() == ["tr-9", "tr-31"], "a rejected annotation leaves no trace"
    reopened.close()


def runs(version: str, passed: int, total: int) -> list[tuple[str, str]]:
    """Judged traces for one version: the rest are WARN, then FAIL."""
    warn = (total - passed + 1) // 2
    return [(version, "PASS")] * passed + [(version, "WARN")] * warn + [(version, "FAIL")] * (total - passed - warn)


@pytest.mark.skip("Part 3")
def test_bisect_prompt_versions() -> None:
    """Trace the regression to the prompt version that introduced it."""
    assert bisect_versions(runs("v1.9", 11, 12) + runs("v1.10", 6, 12), "v1.9").culprit == "v1.10", (
        "v1.10 comes after v1.9"
    )
    mostly_warn = runs("v3.0", 12, 12) + [("v3.1", "PASS")] * 10 + [("v3.1", "WARN")] * 2
    assert bisect_versions(mostly_warn, "v3.0").culprit == "v3.1", "only a PASS verdict counts as a pass"
    drift = runs("v4.0", 36, 40) + runs("v4.1", 34, 40) + runs("v4.2", 33, 40) + runs("v4.3", 31, 40)
    drifted = bisect_versions(drift, "v4.0")
    assert drifted.culprit == "v4.3", "compare every version with the known-good rate, so a slow drift shows up"
    assert drifted == Bisection("v4.2", "v4.3", ["v4.3"]), (
        "suspects run from just after the last good version to the culprit"
    )

    results = (
        runs("v1.12", 1, 2)
        + runs("v1.2", 2, 12)
        + runs("v1.8", 18, 20)
        + runs("v1.13", 15, 15) + [("v1.13", "WARN")] * 5
        + runs("v1.9", 3, 5)
        + runs("v1.11", 8, 10)
        + runs("v1.10", 17, 20)
        + runs("v1.14", 19, 20)
    )
    found = bisect_versions(results, "v1.8", min_traces=10, max_drop=10)
    assert found.culprit not in ("v1.2", "v1.9", "v1.12"), (
        "only a conclusive version after the known-good one can be the culprit"
    )
    assert found.culprit != "v1.11", "a drop of exactly max_drop points is not a regression"
    assert found.culprit == "v1.13", "the culprit is the first conclusive version that regressed"
    assert found.last_good == "v1.11", (
        "last_good is the newest conclusive version before the culprit; exactly min_traces traces is conclusive"
    )
    assert found == Bisection(last_good="v1.11", culprit="v1.13", suspects=["v1.12", "v1.13"]), (
        "suspects run from just after the last good version to the culprit"
    )

    healthy = runs("v2.0", 34, 50) + runs("v2.1", 29, 50) + runs("v2.2", 7, 9)
    assert bisect_versions(healthy, "v2.0", min_traces=10, max_drop=10) == Bisection("v2.1", None, []), (
        "a drop of exactly max_drop points is not a regression"
    )
    assert bisect_versions(runs("v5.0", 9, 14) + runs("v5.1", 19, 35), "v5.0") == Bisection("v5.1", None, []), (
        "a drop of exactly max_drop points is not a regression"
    )
    assert bisect_versions(runs("v6.0", 10, 11) + runs("v6.1", 21, 26), "v6.0").culprit == "v6.1", (
        "a drop of a fraction of a point more than max_drop is a regression"
    )
    with pytest.raises(ValueError):
        bisect_versions(healthy, "v2.2", min_traces=10, max_drop=10)
    with pytest.raises(ValueError):
        bisect_versions(healthy, "v3.0", min_traces=10, max_drop=10)


def create(ts, trace, span, session, name, **attributes) -> dict:
    return {"kind": "create", "ts": ts, "span": {
        "trace_id": trace, "span_id": span, "session_id": session, "name": name, "attributes": attributes,
    }}


def update(ts, trace, span, status=None, **attributes) -> dict:
    event = {"kind": "update", "ts": ts, "trace_id": trace, "span_id": span}
    if status is not None:
        event["status"] = status
    if attributes:
        event["attributes"] = attributes
    return event


BATCHES = [
    [
        create(10, "t1", "1", "s-a", "invoke_agent"),
        create(11, "t1", "2", "s-a", "chat", tokens=100),
        update(15, "t2", "1", "error", **{"error.reason": "rate_limited"}),
        update(12, "t9", "1", "error"),
        create(13, "t3", "1", "s-b", "invoke_agent"),
    ],
    [
        update(30, "t1", "2", tokens=2600),
        update(20, "t1", "2", tokens=900),
        create(11, "t1", "2", "s-a", "chat", tokens=100),
        update(14, "t3", "1", "ok"),
    ],
    [
        create(5, "t2", "1", "s-b", "invoke_agent"),
    ],
    [
        update(49, "t4", "1", tokens=50),
        create(50, "t4", "1", "s-c", "chat", tokens=10),
        create(40, "t1", "3", "s-a", "tool_call search_tool"),
        update(35, "t1", "2", "error", **{"error.reason": "rate_limited"}),
        update(32, "t1", "2", tokens=2700),
        update(60, "t8", "1", "error"),
    ],
]


def parse_sse(chunk: str) -> dict:
    """Parse one Server-Sent Event the way a browser's EventSource does."""
    fields: dict[str, list[str]] = {}
    for line in chunk.rstrip("\n").split("\n"):
        name, _, value = line.partition(":")
        fields.setdefault(name, []).append(value[1:] if value.startswith(" ") else value)
    return {"id": int(fields["id"][-1]), "event": fields["event"][-1], "data": json.loads("\n".join(fields["data"]))}


def view(event: dict) -> tuple:
    data = event["data"]
    if event["event"] == "dropped":
        return ("dropped", data["updates"])
    return (data["session_id"], data["trace_count"], data["span_count"], data["error_count"], data["tokens"])


@pytest.mark.skip("Part 4")
def test_ingest_stream() -> None:
    """Out-of-order span events become one SSE update per changed session, batch by batch."""
    pulled: list[int] = []

    async def source(batches):
        for i, batch in enumerate(batches):
            pulled.append(i)
            yield batch

    async def run() -> list[tuple[int, str]]:
        return [(len(pulled), chunk) async for chunk in ingest_stream(source(BATCHES), orphan_ttl=2)]

    async def first_only() -> str:
        agen = ingest_stream(source(BATCHES), orphan_ttl=2)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert parse_sse(asyncio.run(first_only()))["event"] == "session"
    assert len(pulled) == 1, "write a batch's events before reading the next batch"

    pulled.clear()
    out = asyncio.run(run())
    assert all(chunk.endswith("\n\n") and chunk.count("\n\n") == 1 for _, chunk in out), (
        "yield one complete SSE event at a time"
    )
    events = [(batch, parse_sse(chunk)) for batch, chunk in out]
    assert [e["id"] for _, e in events] == list(range(1, len(events) + 1)), "ids count up across the whole stream"
    assert set(events[0][1]["data"]) == set(SessionSummary.__dataclass_fields__), "data is the session's summary"

    def batch(n: int) -> list[tuple]:
        return [view(e) for b, e in events if b == n]

    assert batch(1) == [("s-a", 1, 2, 0, 100), ("s-b", 1, 1, 0, 0)], (
        "after a batch, one event per changed session, in session_id order"
    )
    assert "dropped" not in [row[0] for row in batch(1) + batch(2)], (
        "an update waits orphan_ttl more batches before it is dropped"
    )
    assert "s-b" not in [row[0] for row in batch(2)], "a session whose summary did not change gets no event"
    assert batch(2) == [("s-a", 1, 2, 0, 2600)], (
        "each field keeps the value with the latest ts, and a retried create changes nothing"
    )
    assert batch(3)[0] == ("s-b", 2, 2, 1, 0), "an update that arrived before its span is applied when the span arrives"
    assert batch(3) == [("s-b", 2, 2, 1, 0), ("dropped", 1)], (
        "an update still waiting after orphan_ttl more batches is dropped"
    )
    assert [row[0] for row in batch(4)][:2] == ["s-a", "s-c"], (
        "after a batch, one event per changed session, in session_id order"
    )
    assert batch(4)[0] == ("s-a", 1, 3, 1, 2700), "the status and each attribute keep their own latest ts"
    assert batch(4)[1] == ("s-c", 1, 1, 0, 10), "an update older than its span's create does not override it"
    assert batch(4)[2:] == [("dropped", 1)], "updates still waiting when the batches run out are dropped too"


def trace(trace_id: str, *rows: tuple) -> list[Span]:
    """rows: (span_id, parent_id, name, start_ns)."""
    return [Span(trace_id, sid, "s", name, parent, start) for sid, parent, name, start in rows]


AGENT = "invoke_agent(chat,tool_call search_tool,chat)"


@pytest.mark.skip("Part 5")
def test_trace_clusters() -> None:
    """Traces group by the shape of their span tree; rare shapes are flagged."""
    r1 = trace("r1", ("4", "1", "chat", 30), ("3", "1", "chat", 10), ("1", None, "invoke_agent", 0),
               ("2", "1", "tool_call search_tool", 20))
    r2 = trace("r2", ("1", None, "invoke_agent", 0), ("3", "1", "tool_call search_tool", 10),
               ("2", "1", "chat", 10), ("4", "1", "chat", 30))
    r3 = trace("r3", ("1", None, "invoke_agent", 0), ("2", "1", "chat", 1), ("3", "1", "tool_call search_tool", 2),
               ("4", "1", "chat", 3))
    r4 = trace("r4", ("1", None, "invoke_agent", 0), ("2", "1", "chat", 1), ("3", "1", "tool_call web_fetch", 2),
               ("4", "1", "chat", 3))
    r5 = trace("r5", ("3", "9", "chat", 5), ("1", None, "invoke_agent", 0), ("2", "1", "chat", 1))
    r6 = trace("r6", ("1", None, "invoke_agent", 0), ("2", "1", "chat(retry)", 1))
    r7 = trace("r7", ("1", None, "invoke_agent", 0), ("2", "1", "chat", 1), ("3", "2", "retry", 2))
    r8 = trace("r8", ("1", None, "invoke_agent", 0), ("2", "1", "chat", 4), ("3", "2", "retry", 6))

    assert signature(r1) == AGENT, "children are ordered by start_ns"
    assert signature(r2) == AGENT, "children are ordered by start_ns, then span_id"
    assert signature(r5) == "invoke_agent(chat),chat", (
        "a span whose parent is missing is a root of its own; roots are ordered like children"
    )
    assert signature(r6) == "invoke_agent(chat\\(retry\\))", "names are escaped, so different trees never share a signature"
    assert signature(trace("x", ("1", None, "a,b\\c", 0))) == "a\\,b\\\\c", "commas and backslashes are escaped too"

    clusters = cluster_traces(r1 + r4 + r6 + r8 + r2 + r5 + r7 + r3, min_share=0.25)
    assert [c.trace_ids for c in clusters] == [["r1", "r2", "r3"], ["r8", "r7"], ["r5"], ["r4"], ["r6"]], (
        "span ids are only unique within a trace; clusters come largest first, then by signature;"
        " trace ids keep the order they first appear in"
    )
    assert clusters == [
        Cluster(AGENT, ["r1", "r2", "r3"], False),
        Cluster("invoke_agent(chat(retry))", ["r8", "r7"], False),
        Cluster("invoke_agent(chat),chat", ["r5"], True),
        Cluster("invoke_agent(chat,tool_call web_fetch,chat)", ["r4"], True),
        Cluster("invoke_agent(chat\\(retry\\))", ["r6"], True),
    ], "a cluster is anomalous below min_share; exactly min_share is not anomalous"
    assert [c.anomalous for c in cluster_traces(r3 + r4 + r1 + r2, min_share=0.3)] == [False, True], (
        "a cluster's share is its traces out of all the traces"
    )

    with pytest.raises(ValueError):
        signature(trace("c1", ("1", "2", "chat", 0), ("2", "1", "chat", 1)))
    with pytest.raises(ValueError):
        signature(trace("c2", ("1", None, "invoke_agent", 0), ("2", "3", "chat", 1), ("3", "2", "chat", 2)))
    with pytest.raises(ValueError):
        signature(trace("c3", ("1", None, "invoke_agent", 0), ("2", "2", "chat", 1)))
