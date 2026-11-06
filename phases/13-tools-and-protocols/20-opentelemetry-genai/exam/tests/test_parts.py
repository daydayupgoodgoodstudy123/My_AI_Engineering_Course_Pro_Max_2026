import dataclasses
import json
import time

import pytest
from genaitrace.agent import Reply, ScriptedLLM, ToolCall, WeatherServer, run_agent
from genaitrace.export import SCOPE, BatchExporter
from genaitrace.metrics import Histogram, metrics
from genaitrace.otlp import from_otlp
from genaitrace.propagate import McpRequest, extract, format_traceparent, inject, parse_traceparent
from genaitrace.semconv import check, scrub
from genaitrace.spanlog import SpanLog
from genaitrace.traces import link
from genaitrace.tracer import FakeClock, SeededIds, Span, SpanContext, Tracer
from genaitrace.waterfall import critical_path, self_times

T0 = 1_767_225_600_000_000_000  # 2026-01-01T00:00:00Z in Unix nanoseconds, far above 2**53
MS = 1_000_000
SEC = 1_000_000_000
UPSTREAM = SpanContext("4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7")
QUESTION = "What's the weather in Bengaluru, Tokyo and Zurich?"
ANSWER = "Bengaluru 28 C, Tokyo 12 C, Zurich 4 C."


def weather_llm(clock, cities=("Bengaluru", "Tokyo", "Zurich")) -> ScriptedLLM:
    """The lesson's run: one chat asks for the weather in every city, the next one answers."""
    calls = [ToolCall(f"call_{i}", "get_weather", {"city": city}) for i, city in enumerate(cities, 1)]
    return ScriptedLLM(
        clock,
        [
            Reply(tool_calls=calls, input_tokens=16, output_tokens=24, response_id="resp_1"),
            Reply(text=ANSWER, input_tokens=230, output_tokens=64, response_id="resp_2"),
        ],
    )


def shape(trace, spans=None) -> list:
    """The trace as nested (name, kind, children) tuples, from its roots down."""
    spans = trace.roots if spans is None else spans
    return [(s.name, s.kind, shape(trace, trace.children_of(s))) for s in spans]


def names(tree: list) -> list:
    """The same tree without the span kinds."""
    return [(name, names(children)) for name, _, children in tree]


TOOL = ("tool.execute", "INTERNAL", [("mcp.call", "CLIENT", [])])
LESSON_TREE = [
    ("agent.invoke_agent", "INTERNAL", [("llm.chat", "CLIENT", []), TOOL, TOOL, TOOL, ("llm.chat", "CLIENT", [])])
]


@pytest.mark.skip("Part 1")
def test_agent_trace() -> None:
    """One agent run is one trace, with the lesson's span kinds, and content stays out unless asked for."""
    clock = FakeClock(T0)
    tracer = Tracer(clock, SeededIds(1), env={})
    assert run_agent(tracer, weather_llm(clock), WeatherServer(clock), QUESTION) == ANSWER
    spans = tracer.finished()
    traces = link(spans)
    assert len(traces) == 1, "one agent run is one trace"
    assert names(shape(traces[0])) == names(LESSON_TREE), (
        "every span hangs under the span that started it: the agent's chats and tools, each tool's MCP call"
    )
    assert shape(traces[0]) == LESSON_TREE, (
        "a call into another process is a CLIENT span; the agent's own steps are INTERNAL"
    )
    root = traces[0].roots[0]
    assert root.end_ns - root.start_ns == (50 + 3 * (30 + 40) + 50) * MS, "the root covers the whole run"
    assert [e.name for s in spans for e in s.events] == [], (
        "prompts and completions stay out of spans unless content capture is turned on"
    )

    for value in ("0", "true", "1"):
        clock = FakeClock(T0)
        opted = Tracer(clock, SeededIds(2), env={"OTEL_CAPTURE_CONTENT": value})
        run_agent(opted, weather_llm(clock), WeatherServer(clock), QUESTION)
        seen = {(s.name, tuple(e.name for e in s.events)) for s in opted.finished()}
        if value == "1":
            assert seen == {
                ("agent.invoke_agent", ()),
                ("llm.chat", ("gen_ai.content.prompt", "gen_ai.content.completion")),
                ("tool.execute", ("gen_ai.content.tool_call",)),
                ("mcp.call", ()),
            }, "OTEL_CAPTURE_CONTENT=1 turns content capture on"
        else:
            assert {events for _, events in seen} == {()}, (
                f"only OTEL_CAPTURE_CONTENT=1 turns content capture on, not {value!r}"
            )

    # A sub-agent, invoked by an agent in another process that sent a traceparent along.
    clock = FakeClock(T0)
    sub = Tracer(clock, SeededIds(3), env={})
    run_agent(sub, weather_llm(clock), WeatherServer(clock), QUESTION, parent=UPSTREAM)
    sub_traces = link(sub.finished())
    assert [t.trace_id for t in sub_traces] == [UPSTREAM.trace_id], "a sub-agent continues its caller's trace"
    assert [(s.name, s.parent_span_id) for s in sub_traces[0].roots] == [
        ("agent.invoke_agent", UPSTREAM.span_id)
    ], "a span whose parent ran in another process is a root of its trace and keeps its parent's id"
    assert shape(sub_traces[0]) == LESSON_TREE and len(sub_traces[0].spans) == 9

    clock = FakeClock(T0)
    twice = Tracer(clock, SeededIds(4), env={})
    for _ in range(2):
        run_agent(twice, weather_llm(clock), WeatherServer(clock), QUESTION)
    assert [shape(t) for t in link(twice.finished())] == [LESSON_TREE, LESSON_TREE], (
        "every run without a parent starts its own trace"
    )

    # Span ids only need to be unique within a trace.
    clock = FakeClock(T0)
    other = Tracer(clock, SeededIds(5), env={})
    clash = SpanContext(UPSTREAM.trace_id, root.span_id)
    run_agent(other, weather_llm(clock), WeatherServer(clock), QUESTION, parent=clash)
    replayed = [dataclasses.replace(s, trace_id="c" * 32) for s in spans]  # the same span ids, another trace
    mixed = link(spans + other.finished() + replayed)
    assert [shape(t) for t in mixed] == [LESSON_TREE] * 3, "a span links only to a parent in its own trace"
    assert [t.trace_id for t in mixed] == [root.trace_id, UPSTREAM.trace_id, "c" * 32], (
        "traces come in the order their first span appears"
    )

    clock = FakeClock(T0)
    session = Tracer(clock, SeededIds(6), env={})
    cities = [f"city-{i:04d}" for i in range(6_500)]
    run_agent(session, weather_llm(clock, cities), WeatherServer(clock), "Weather everywhere, please.")
    long_run = session.finished()
    start = time.perf_counter()
    linked = link(long_run)
    elapsed = time.perf_counter() - start
    assert [len(t.spans) for t in linked] == [3 + 2 * len(cities)]
    assert elapsed < 0.12, "linking should stay fast for a session with thousands of tool calls"


def exact(value):
    """A comparable form of a value that tells 1 from 1.0 and from True, and keeps every float bit."""
    if dataclasses.is_dataclass(value):
        return (type(value).__name__, exact(dataclasses.asdict(value)))
    if isinstance(value, dict):
        return {key: exact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [exact(item) for item in value]
    if isinstance(value, float):
        return ("float", value.hex())
    return (type(value).__name__, value)


TRICKY = {
    "gen_ai.operation.name": "chat",
    "gen_ai.provider.name": "openai",
    "gen_ai.request.model": "gpt-4o",
    "gen_ai.response.model": "gpt-4o-2024-08-06",
    "gen_ai.response.id": "resp_3",
    "gen_ai.usage.input_tokens": 1,
    "gen_ai.usage.output_tokens": 0,
    "acme.request.temperature": 1.0,
    "acme.request.top_p": 0.1 + 0.2,
    "acme.request.stream": True,
    "acme.request.seed": 2**53 + 1,
    "acme.request.stop": ["\n\n", "END"],
    "acme.retry.backoff_s": [0.5, 1.0, 2.0],
    "acme.retry.statuses": [429, 503],
    "acme.limits": [2**63 - 1, -(2**63)],
    "acme.flags": [True, False],
    "acme.tags": [],
    "acme.note": "",
}


@pytest.mark.skip("Part 2")
def test_span_log_roundtrip(tmp_path) -> None:
    """Spans come back from the log exactly as they went in, and other tools can read the log too."""
    clock = FakeClock(T0 + 123_456_789)
    tracer = Tracer(clock, SeededIds(20), env={"OTEL_CAPTURE_CONTENT": "1"})
    run_agent(tracer, weather_llm(clock), WeatherServer(clock), QUESTION)
    late = tracer.start_span("llm.chat", "CLIENT", parent=tracer.finished()[-1], attrs=TRICKY)
    for city in ("Tokyo", "Zurich"):  # one completion that asked for two tool calls: two events, one name
        clock.sleep(1)
        tracer.add_event(late, "gen_ai.content.tool_call", {"content": json.dumps({"city": city})})
    tracer.add_event(late, "acme.retry", {"attempt": 2, "backoff_s": 0.5, "final": False})
    clock.sleep(7)
    tracer.finish(late)
    spans = tracer.finished()

    path = tmp_path / "spans.jsonl"
    fresh = SpanLog(path)
    assert fresh.spans() == [], "a new log holds no spans"
    fresh.close()
    for batch in (spans[:4], spans[4:]):
        log = SpanLog(path)
        for span in batch:
            log.append(span)
        log.close()
    log = SpanLog(path)
    assert exact(log.spans()) == exact(spans), "spans read back exactly as they were appended, across reopens"
    log.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(spans), "one span per line"
    as_doubles = [json.loads(line, parse_int=float) for line in lines]  # how JavaScript or jq reads the file
    assert [
        (int(d["startTimeUnixNano"]), int(d["endTimeUnixNano"]), [int(e["timeUnixNano"]) for e in d["events"]])
        for d in as_doubles
    ] == [(s.start_ns, s.end_ns, [e.time_ns for e in s.events]) for s in spans], (
        "nanosecond timestamps survive a reader whose numbers are doubles"
    )
    values = {a["key"]: a["value"] for a in as_doubles[-1]["attributes"]}
    assert int(values["acme.request.seed"]["intValue"]) == 2**53 + 1, (
        "64-bit integers survive a reader whose numbers are doubles"
    )
    assert [d["parentSpanId"] for d in as_doubles] == [s.parent_span_id or "" for s in spans], (
        "a span with no parent has an empty parentSpanId"
    )

    before = path.read_bytes()
    log = SpanLog(path)
    unfinished = tracer.start_span("tool.execute", "INTERNAL", parent=late)
    with pytest.raises(ValueError):
        log.append(unfinished)
    for bad in (2**63, -(2**63) - 1, [True, 1], [1, True], [1, 2.5], [["Tokyo"]], None, {"city": "Tokyo"}):
        span = tracer.start_span("tool.execute", "INTERNAL", parent=late, attrs={"acme.bad": bad})
        tracer.finish(span)
        try:
            log.append(span)
        except ValueError:
            continue
        pytest.fail(f"an attribute value of {bad!r} cannot be logged")
    log.close()
    assert path.read_bytes() == before, "a span that cannot be logged leaves the log as it was"


def buckets(histogram: Histogram) -> tuple[dict[int, int], int]:
    """The non-empty buckets, by index, and the total count."""
    return {i: n for i, n in enumerate(histogram.counts) if n}, histogram.count


@pytest.mark.skip("Part 3")
def test_conventions_and_metrics() -> None:
    """Spans meet the GenAI conventions, content leaves only when allowed, and the metrics add up."""
    clock = FakeClock(T0)
    tracer = Tracer(clock, SeededIds(30), env={"OTEL_CAPTURE_CONTENT": "1"})
    run_agent(tracer, weather_llm(clock), WeatherServer(clock), QUESTION)
    run = tracer.finished()
    assert check(run) == [], "the lesson's agent follows the conventions"

    def made(name: str, kind: str, attrs: dict, duration_ns: int, events: tuple = ()) -> Span:
        span = tracer.start_span(name, kind, attrs=attrs)
        for event, event_attrs in events:
            tracer.add_event(span, event, event_attrs)
        clock.sleep(duration_ns)
        tracer.finish(span)
        return span

    mini = {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "openai",
        "gen_ai.request.model": "gpt-4o-mini",
        "gen_ai.response.model": "gpt-4o-mini-2024-07-18",
        "gen_ai.response.id": "resp_9",
    }
    events = (
        ("acme.retry", {"attempt": 1}),
        ("gen_ai.content.prompt", {"content": "Wie warm ist es in Zürich?"}),
        ("acme.cache.miss", {}),
    )
    unanswered = {"gen_ai.usage.input_tokens": 4096, "gen_ai.usage.output_tokens": 0}
    filtered = made("llm.chat", "CLIENT", {**mini, **unanswered}, 2_500 * MS, events)
    sloppy = {key: value for key, value in mini.items() if key != "gen_ai.response.id"}
    sloppy = made("llm.chat", "INTERNAL", {**sloppy, "gen_ai.usage.input_tokens": 1, "gen_ai.usage.output_tokens": 65537}, 10 * SEC)
    slow = made("llm.stream", "CLIENT", {**mini, "gen_ai.usage.input_tokens": 65536, "gen_ai.usage.output_tokens": 1}, 10 * SEC + 1)
    # The stream was cut off after the prompt was counted, before any output came back.
    cancelled = made("llm.chat", "CLIENT", {**mini, "gen_ai.usage.input_tokens": 300}, SEC)
    no_call_id = made("tool.search", "INTERNAL", {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "search_docs"}, 75 * MS)
    blank = made("mcp.call", "CLIENT", {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.call.id": ""}, 5 * MS)
    remote = made("agent.invoke_agent", "CLIENT", {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "planner"}, SEC)
    vendor = {"gen_ai.operation.name": "chat.completions", "gen_ai.request.model": "gpt-4o-mini"}
    vendor = made("llm.chat", "CLIENT", {**vendor, "gen_ai.usage.input_tokens": 3, "gen_ai.usage.output_tokens": 5}, SEC)
    plain = made("GET /forecast", "CLIENT", {"net.peer.name": "api.weather.example"}, SEC)

    assert check([filtered]) == [], "0 output tokens is a value, and the served model may differ from the requested one"
    assert check([no_call_id]) == [(no_call_id.span_id, "missing gen_ai.tool.call.id")], (
        "a tool span without its call id is reported"
    )
    assert check([blank]) == [
        (blank.span_id, "missing gen_ai.tool.name"),
        (blank.span_id, "missing gen_ai.tool.call.id"),
    ], "an empty string counts as missing; missing attributes come in REQUIRED order"
    assert check([sloppy, remote]) == [
        (sloppy.span_id, "kind INTERNAL not allowed for chat"),
        (sloppy.span_id, "missing gen_ai.response.id"),
        (remote.span_id, "kind CLIENT not allowed for invoke_agent"),
        (remote.span_id, "missing gen_ai.agent.id"),
    ], "a wrong span kind is reported before the missing attributes"
    assert check([vendor]) == [(vendor.span_id, "unknown operation chat.completions")], (
        "an operation without rules is reported, and nothing else about that span"
    )
    assert check([plain]) == [], "a span without gen_ai.operation.name is not a GenAI span"
    extra = [filtered, sloppy, slow, cancelled, no_call_id, blank, remote, vendor, plain]
    assert [problem for _, problem in check(run + extra)] == [
        "kind INTERNAL not allowed for chat",
        "missing gen_ai.response.id",
        "missing gen_ai.usage.output_tokens",
        "missing gen_ai.tool.call.id",
        "missing gen_ai.tool.name",
        "missing gen_ai.tool.call.id",
        "kind CLIENT not allowed for invoke_agent",
        "missing gen_ai.agent.id",
        "unknown operation chat.completions",
    ], "problems come in span order"

    everything = run + extra
    before = exact(everything)
    clean = scrub(everything, capture_content=False)
    assert [(s.span_id, [e.name for e in s.events]) for s in clean] == [
        (s.span_id, ["acme.retry", "acme.cache.miss"] if s is filtered else []) for s in everything
    ], "with content capture off only the content events are dropped"
    assert exact(everything) == before, "scrub leaves the spans it was given as they were"
    assert exact(scrub(everything, capture_content=True)) == before, "with content capture on, content may leave"

    histogram = Histogram((1, 4, 16))
    for value in (0, 1, 2, 4, 16, 17):
        histogram.record(value)
    assert (histogram.counts, histogram.count, histogram.sum) == ([2, 2, 1, 1], 6, 40), (
        "a value on a bound goes in the bucket that bound closes; above the last bound, in the last slot"
    )

    m = metrics(everything)
    assert set(m) == {"gen_ai.client.token.usage", "gen_ai.client.operation.duration", "gen_ai.tool.execution.duration"}
    tokens = m["gen_ai.client.token.usage"]
    assert {kind: buckets(h) for kind, h in tokens.items()} == {
        "input": ({0: 1, 2: 1, 4: 1, 5: 1, 6: 1, 8: 1}, 6),
        "output": ({0: 2, 3: 2, 9: 1}, 5),
    }, "token usage is split into input and output, each count is a sample of its own, and 0 tokens is a sample too"
    assert (tokens["input"].sum, tokens["output"].sum) == (70_179, 65_626)
    durations = m["gen_ai.client.operation.duration"]
    assert {model: buckets(h) for model, h in durations.items()} == {
        "gpt-4o": ({3: 2}, 2),
        "gpt-4o-mini": ({8: 1, 9: 1, 12: 1, 13: 1}, 4),
    }, "chat durations in seconds, by requested model; a value on a bound closes that bucket"
    assert durations["gpt-4o-mini"].sum == pytest.approx(23.500000001, abs=1e-12)
    tools = m["gen_ai.tool.execution.duration"]
    assert {tool: h.count for tool, h in tools.items()} == {"get_weather": 3, "search_docs": 1}, (
        "one sample per tool call, by tool name: the MCP round trip inside it is not a second call"
    )
    assert {tool: buckets(h)[0] for tool, h in tools.items()} == {"get_weather": {4: 3}, "search_docs": {4: 1}}, (
        "tool durations in seconds; a duration exactly on a bound stays in the bucket that bound closes"
    )
    assert tools["get_weather"].sum == pytest.approx(0.21, abs=1e-12)


def collector(clock, received: list):
    """A stand-in OTLP collector: records when each request arrived and what it held."""

    def send(body: bytes) -> None:
        assert isinstance(body, bytes), "send() gets each request as UTF-8 bytes"
        received.append((clock(), json.loads(body)))

    return send


def unpack(request: dict) -> tuple[str, list[Span]]:
    """The service name and the spans of one OTLP/JSON export request."""
    (resource_spans,) = request["resourceSpans"]
    (scope_spans,) = resource_spans["scopeSpans"]
    assert scope_spans["scope"] == SCOPE
    attrs = {a["key"]: a["value"] for a in resource_spans["resource"]["attributes"]}
    return attrs["service.name"]["stringValue"], [from_otlp(s) for s in scope_spans["spans"]]


def traceparents(server: WeatherServer) -> list:
    """What each request the server got carried: the traceparent header, and params._meta.traceparent."""
    return [
        (r.headers.get("traceparent"), r.message.get("params", {}).get("_meta", {}).get("traceparent"))
        for r in server.requests
    ]


GOOD = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


@pytest.mark.skip("Part 4")
def test_propagation_and_export() -> None:
    """The trace follows the call into the MCP server, and both sides ship spans in OTLP/JSON batches."""
    assert parse_traceparent(GOOD) == UPSTREAM
    assert parse_traceparent(GOOD[:-2] + "00") == UPSTREAM, "an unsampled traceparent still carries the context"
    bad = [
        None,
        42,
        "",
        "garbage",
        GOOD.upper(),
        GOOD + "\n",
        GOOD + "-00",
        "01" + GOOD[2:],
        "ff" + GOOD[2:],
        "00-" + "0" * 32 + "-00f067aa0ba902b7-01",
        "00-4bf92f3577b34da6a3ce929d0e0e4736-" + "0" * 16 + "-01",
        "00-4bf92f3577b34da6a3ce929d0e0e473-00f067aa0ba902b7-01",
        "00-0x4bf92f3577b34da6a3ce929d0e0e47-00f067aa0ba902b7-01",
        "00-4bf92f3577b34da6a3ce929d0e0e4736-+0f067aa0ba902b7-01",
        "00-4bf92f35_7b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-0g",
        "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-0A",
    ]
    for value in bad:
        assert parse_traceparent(value) is None, f"not a usable traceparent: {value!r}"

    clock = FakeClock(T0)
    call = Tracer(clock, SeededIds(40), env={}).start_span("mcp.call", "CLIENT")
    stdio = McpRequest(
        "stdio",
        {
            "jsonrpc": "2.0",
            "id": "call_1",
            "method": "tools/call",
            "params": {"name": "get_weather", "arguments": {"city": "Tokyo"}, "_meta": {"progressToken": "p-1"}},
        },
    )
    sent = inject(stdio, call)
    assert sent.message["params"]["_meta"] == {"progressToken": "p-1", "traceparent": format_traceparent(call)}, (
        "over stdio the traceparent goes in params._meta, next to what is already there"
    )
    assert sent.headers == {} and stdio.message["params"]["_meta"] == {"progressToken": "p-1"}, (
        "stdio has no headers, and the caller's request is left as it was"
    )
    assert extract(sent) == call.context
    listing = inject(McpRequest("stdio", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}), call)
    assert listing.message["params"] == {"_meta": {"traceparent": format_traceparent(call)}}
    http = McpRequest(
        "http",
        {"jsonrpc": "2.0", "id": "call_2", "method": "tools/call", "params": {"name": "get_weather", "arguments": {}}},
        {"content-type": "application/json"},
    )
    sent = inject(http, call)
    assert sent.headers == {"content-type": "application/json", "traceparent": format_traceparent(call)}, (
        "over HTTP the traceparent is a header"
    )
    assert sent.message == http.message and http.headers == {"content-type": "application/json"}, (
        "over HTTP the message is not touched, and the caller's request is left as it was"
    )

    parents = Tracer(clock, SeededIds(47), env={})
    first = parents.start_span("mcp.call", "CLIENT", parent=UPSTREAM)
    second = parents.start_span("mcp.call", "CLIENT", parent=SpanContext("b" * 32, "c" * 16))
    for transport in ("http", "stdio"):
        base = McpRequest(
            transport,
            {"jsonrpc": "2.0", "id": "shared-template", "method": "tools/call", "params": {
                "name": "get_weather", "arguments": {"city": "Tokyo"},
                "_meta": {"progressToken": "keep-me", "traceparent": format_traceparent(call)},
            }},
            {"content-type": "application/json", "traceparent": GOOD},
        )
        before = dataclasses.asdict(base)
        one, two = inject(base, first), inject(base, second)
        assert (extract(one), extract(two)) == (first.context, second.context), (
            "each injection carries the current span, replacing any context in its active carrier"
        )
        assert extract(one) == first.context, "a later injection cannot rewrite an earlier request's context"
        assert dataclasses.asdict(base) == before, "injecting different spans leaves the shared request template unchanged"
        if transport == "http":
            assert one.message == two.message == base.message, "HTTP injection leaves every message field unchanged"
            assert one.headers == {**base.headers, "traceparent": format_traceparent(first)}
            assert two.headers == {**base.headers, "traceparent": format_traceparent(second)}
        else:
            assert one.headers == two.headers == base.headers, "stdio injection leaves the inactive HTTP headers unchanged"
            assert one.message["params"]["_meta"] == {"progressToken": "keep-me", "traceparent": format_traceparent(first)}
            assert two.message["params"]["_meta"] == {"progressToken": "keep-me", "traceparent": format_traceparent(second)}
        receiver = WeatherServer(clock, transport=transport, tracer=Tracer(clock, SeededIds(48), env={}))
        for request in (one, two):
            assert receiver.handle(request)["result"]["content"][0]["text"] == "Tokyo: 12 C"
        assert [(s.trace_id, s.parent_span_id) for s in receiver.tracer.finished()] == [
            (first.trace_id, first.span_id), (second.trace_id, second.span_id),
        ], "each receiver span continues its own call's context and uses that call's span id as parent"
        for active in (None, "garbage"):
            message = {"params": {"_meta": {"traceparent": format_traceparent(second)}}}
            headers = {"traceparent": format_traceparent(first)}
            if transport == "http":
                headers = {} if active is None else {"traceparent": active}
            else:
                message = {"params": {"_meta": {}}} if active is None else {"params": {"_meta": {"traceparent": active}}}
            assert extract(McpRequest(transport, message, headers)) is None, (
                "an absent or unusable active carrier never falls back to the other transport"
            )

    # The lesson's run, with the MCP server as a process of its own that traces and exports too.
    received: list = []
    agent_exporter = BatchExporter(collector(clock, received), service_name="research-agent", clock=clock, max_batch=4)
    server_exporter = BatchExporter(collector(clock, received), service_name="weather-mcp", clock=clock, max_batch=2)
    agent = Tracer(clock, SeededIds(41), env={}, on_end=agent_exporter.on_end)
    server = WeatherServer(clock, tracer=Tracer(clock, SeededIds(42), env={}, on_end=server_exporter.on_end))
    run_agent(agent, weather_llm(clock), server, QUESTION)
    calls = [s for s in agent.finished() if s.name == "mcp.call"]
    assert traceparents(server) == [(None, format_traceparent(c)) for c in calls], (
        "every tools/call over stdio carries its mcp.call span as the parent, in params._meta"
    )
    agent_requests = [(at, spans) for at, request in received for name, spans in [unpack(request)] if name == "research-agent"]
    assert [len(spans) for _, spans in agent_requests] == [4, 4], "a full batch goes out at once"
    assert all(at == spans[-1].end_ns for at, spans in agent_requests), "a batch goes out the moment it fills"
    agent_exporter.shutdown()
    server_exporter.shutdown()
    agent_exporter.shutdown()
    by_service: dict[str, list[Span]] = {}
    for _, request in received:
        name, spans = unpack(request)
        assert 1 <= len(spans) <= (4 if name == "research-agent" else 2), "no request is empty or over max_batch"
        by_service.setdefault(name, []).extend(spans)
    assert exact(by_service["research-agent"]) == exact(agent.finished()), (
        "every agent span is exported once, in the order the spans ended"
    )
    assert exact(by_service["weather-mcp"]) == exact(server.tracer.finished())
    assert [(s.trace_id, s.parent_span_id) for s in by_service["weather-mcp"]] == [
        (c.trace_id, c.span_id) for c in calls
    ], "the server's spans continue the agent's trace, under the mcp.call spans"

    over_http = WeatherServer(clock, transport="http", tracer=Tracer(clock, SeededIds(43), env={}))
    agent = Tracer(clock, SeededIds(44), env={})
    run_agent(agent, weather_llm(clock), over_http, QUESTION)
    calls = [s for s in agent.finished() if s.name == "mcp.call"]
    assert traceparents(over_http) == [(format_traceparent(c), None) for c in calls], (
        "over Streamable HTTP the traceparent travels as a header"
    )
    assert [s.parent_span_id for s in over_http.tracer.finished()] == [c.span_id for c in calls]

    legacy = WeatherServer(clock, tracer=Tracer(clock, SeededIds(45), env={}))
    for value in (GOOD.upper(), "00-" + "0" * 32 + "-00f067aa0ba902b7-01", 42):
        message = {
            "jsonrpc": "2.0",
            "id": "x",
            "method": "tools/call",
            "params": {"name": "get_weather", "arguments": {"city": "Zurich"}, "_meta": {"traceparent": value}},
        }
        assert legacy.handle(McpRequest("stdio", message))["result"]["content"][0]["text"] == "Zurich: 4 C"
    started = legacy.tracer.finished()
    assert [s.parent_span_id for s in started] == [None] * 3 and len({s.trace_id for s in started}) == 3, (
        "a malformed traceparent starts a new trace instead of failing the call"
    )

    received.clear()
    exporter = BatchExporter(collector(clock, received), service_name="research-agent", clock=clock, max_batch=3, max_delay_ns=2 * SEC)
    tracer = Tracer(clock, SeededIds(46), env={}, on_end=exporter.on_end)

    def end(name: str) -> None:
        tracer.finish(tracer.start_span(name, "INTERNAL"))

    def batches() -> list[list[str]]:
        return [[s.name for s in unpack(request)[1]] for _, request in received]

    exporter.tick()
    still_running = tracer.start_span("still-running", "INTERNAL")
    recorded = tracer.start_span("a", "INTERNAL", start_ns=clock() - 4 * SEC)
    tracer.finish(recorded, end_ns=clock() - 3 * SEC)  # ended with the time it really ended, 3 s ago
    clock.sleep(SEC)
    end("b")
    clock.sleep(SEC - 1)
    exporter.tick()
    assert batches() == [], "nothing goes out before the oldest span has waited max_delay_ns since it was queued"
    clock.sleep(1)
    exporter.tick()
    exporter.tick()
    assert batches() == [["a", "b"]], (
        "tick sends the waiting spans once the oldest has waited max_delay_ns, and never an empty request"
    )
    clock.sleep(5 * SEC)
    end("c")
    clock.sleep(2 * SEC - 1)
    exporter.tick()
    assert batches() == [["a", "b"]], "the wait starts when a span is queued, not at the last request"
    clock.sleep(1)
    exporter.tick()
    for name in ("d", "e", "f", "g"):
        end(name)
    assert batches() == [["a", "b"], ["c"], ["d", "e", "f"]], "a full batch goes out at once"
    exporter.shutdown()
    end("h")
    tracer.finish(still_running)
    exporter.shutdown()
    clock.sleep(2 * SEC)
    exporter.tick()
    assert batches() == [["a", "b"], ["c"], ["d", "e", "f"], ["g"]], (
        "shutdown sends what is left, and spans that end after it are dropped"
    )


def sid(n: int) -> str:
    return f"{n:016x}"


def span(name: str, n: int, parent, start_ms: int, end_ms: int, trace_id: str, kind: str = "INTERNAL") -> Span:
    return Span(name, kind, trace_id, sid(n), None if parent is None else sid(parent), T0 + start_ms * MS, T0 + end_ms * MS)


SLOW, FAST, SERIAL, TIED = "5" * 32, "f" * 32, "3" * 32, "7" * 32
WATERFALL = [
    # 30 s: three tools run at once and the Tokyo call waits for a cold MCP server. The server's clock
    # is off by a few milliseconds, so its spans can stick out of the client spans they belong to.
    span("agent.invoke_agent", 1, None, 0, 30_000, SLOW),
    span("llm.chat", 2, 1, 0, 1_200, SLOW, "CLIENT"),
    span("tool.execute", 3, 1, 1_250, 1_900, SLOW),
    span("mcp.call", 4, 3, 1_280, 1_880, SLOW, "CLIENT"),
    span("mcp.server tools/call", 5, 4, 1_290, 1_870, SLOW, "SERVER"),
    span("tool.execute", 6, 1, 1_200, 28_400, SLOW),
    span("mcp.call", 7, 6, 1_230, 28_380, SLOW, "CLIENT"),
    span("mcp.server tools/call", 8, 7, 26_300, 28_420, SLOW, "SERVER"),
    span("tool.execute", 9, 1, 1_300, 1_800, SLOW),
    span("mcp.call", 10, 9, 1_330, 1_790, SLOW, "CLIENT"),
    span("mcp.server tools/call", 11, 10, 1_320, 1_780, SLOW, "SERVER"),
    span("llm.chat", 12, 1, 28_450, 30_000, SLOW, "CLIENT"),
    span("mcp.server tools/call", 13, 99, 1_500, 1_560, SLOW, "SERVER"),  # its client span never arrived
    # 3.28 s: a sub-agent runs two tools at once.
    span("agent.invoke_agent", 21, None, 0, 3_280, FAST),
    span("llm.chat", 22, 21, 0, 900, FAST, "CLIENT"),
    span("subagent.invoke", 24, 21, 900, 2_100, FAST),
    span("tool.execute", 25, 24, 900, 2_000, FAST),
    span("tool.execute", 26, 24, 950, 2_100, FAST),
    span("llm.chat", 27, 21, 2_100, 3_280, FAST, "CLIENT"),
    # 2.3 s: the agent's own work around a tool call, then a chat that starts a cache write it does not wait for.
    span("agent.invoke_agent", 41, None, 0, 2_300, SERIAL),
    span("tool.execute", 42, 41, 0, 1_200, SERIAL),
    span("mcp.call", 43, 42, 300, 900, SERIAL, "CLIENT"),
    span("llm.chat", 44, 41, 1_200, 2_200, SERIAL, "CLIENT"),
    span("acme.cache.write", 45, 44, 2_250, 2_290, SERIAL),
    # Two chats of the same length.
    span("agent.invoke_agent", 31, None, 0, 2_000, TIED),
    span("llm.chat", 33, 31, 0, 1_000, TIED, "CLIENT"),
    span("llm.chat", 32, 31, 1_000, 2_000, TIED, "CLIENT"),
]


def ms(own: dict, *numbers: int) -> dict:
    """Self times in milliseconds for the spans with these numbers."""
    return {n: own[sid(n)] / MS for n in numbers}


def chain(trace, root=None) -> list[int]:
    """The span numbers along the heaviest chain from root (the trace's local root by default)."""
    root = root or next(s for s in trace.roots if s.parent_span_id is None)
    return [int(s.span_id, 16) for s in critical_path(trace, root)]


@pytest.mark.skip("Part 5")
def test_where_the_time_went() -> None:
    """Self time and the heaviest chain show where a slow run spent its time."""
    as_exported = sorted(WATERFALL, key=lambda s: s.end_ns)  # a collector hands spans over as they ended
    traces = {t.trace_id: t for t in link(as_exported)}
    slow, fast, serial, tied = (traces[t] for t in (SLOW, FAST, SERIAL, TIED))

    own = self_times(slow)
    assert set(own) == {s.span_id for s in slow.spans}, "every span has a self time"
    assert ms(own, 1) == {1: 50}, "self time is the time no child covers: children at the same time count once"
    assert ms(own, 7, 10) == {7: 25_070, 10: 10}, "a child that sticks out of its parent covers only the part inside it"
    assert ms(own, 2, 3, 4, 5, 6, 8, 9, 11, 12, 13) == {
        2: 1_200, 3: 50, 4: 20, 5: 580, 6: 50, 8: 2_120, 9: 40, 11: 460, 12: 1_550, 13: 60
    }
    assert chain(slow) == [1, 6, 7, 8], "the heaviest chain runs through the Tokyo call that waited for the cold server"
    assert [chain(slow, r) for r in slow.roots if r.parent_span_id is not None] == [[13]], (
        "a span whose parent never arrived heads a chain of its own"
    )

    assert ms(self_times(fast), 21, 22, 24, 25, 26, 27) == {21: 0, 22: 900, 24: 0, 25: 1_100, 26: 1_150, 27: 1_180}
    assert chain(fast) == [21, 27], "the chain goes by the self time a child's subtree adds up to, not by its duration"
    assert ms(self_times(serial), 41, 42, 43, 44, 45) == {41: 100, 42: 600, 43: 600, 44: 1_000, 45: 40}, (
        "a child entirely outside its parent covers none of it"
    )
    assert chain(serial) == [41, 42, 43], "the chain adds up self times along the way"
    assert chain(tied) == [31, 32], "children that tie go to the smaller span id"
