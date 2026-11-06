import asyncio
import json
import random
import re
import time

import pytest
from semconv.agent import Agent, ModelReply, ToolCall, agent_tool, create_agent, run_agent
from semconv.attribution import ToolErrorReport, ToolErrorRow, tool_errors
from semconv.content_db import SqliteContentStore
from semconv.feed import stream_spans
from semconv.tracer import ExternalContentStore, Span, Tracer, captured_content
from semconv.usage import AgentUsage, Usage, agent_usage

EPOCH_2026 = 1_767_225_600_000_000_000


class FakeClock:
    """Epoch nanoseconds that move forward 1 µs per reading."""

    def __init__(self, start: int = EPOCH_2026) -> None:
        self.now = start

    def __call__(self) -> int:
        self.now += 1_000
        return self.now


def scripted(*replies: ModelReply):
    """A deterministic stand-in for the LLM: returns the given replies in order."""
    queue = list(replies)

    async def model(messages):
        await asyncio.sleep(0)
        return queue.pop(0)

    return model


def tool(result: str, yields: int = 1, fail: Exception | None = None):
    async def call(arguments):
        for _ in range(yields):
            await asyncio.sleep(0)
        if fail is not None:
            raise fail
        return result

    return call


def calls(*names: str) -> tuple[ToolCall, ...]:
    return tuple(ToolCall(name, {"q": name}) for name in names)


def run(coro, timeout: float = 2.0):
    async def bounded():
        return await asyncio.wait_for(coro, timeout)

    try:
        return asyncio.run(bounded())
    except asyncio.TimeoutError:
        pass
    pytest.fail("each line is yielded as soon as its span ends, while the run is still going")


def exact(a, b) -> bool:
    """Equal with the same types all the way down, and dict keys in the same order."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    return a == b


def mk(span_id, parent, op, start, **attributes) -> Span:
    return Span(
        name=op,
        kind="INTERNAL",
        trace_id=1,
        span_id=span_id,
        parent_span_id=parent,
        start_ns=start,
        end_ns=start + 1,
        attributes={"gen_ai.operation.name": op, **attributes},
    )


def ops(spans) -> list:
    """The gen_ai.operation.name of each span, in order."""
    return [s.attributes.get("gen_ai.operation.name") for s in spans]


@pytest.mark.skip("Part 1")
def test_agent_spans() -> None:
    """An agent is created once; each run records the right span names, parents, times and content references."""
    store = ExternalContentStore()
    tracer = Tracer(capture_content=True, content_store=store, clock=FakeClock(), rng=random.Random(1))
    agent = create_agent(
        tracer,
        None,
        "anthropic",
        "claude-opus-4-6",
        tools={"search": tool("3 sources", yields=1), "fetch": tool("<html>", yields=3)},
        data_sources={"search": "corpus://mem0/default"},
    )
    built = ops(tracer.finished)
    model = scripted(
        ModelReply(tool_calls=calls("search", "fetch"), response_model="claude-opus-4-6"),
        ModelReply(text="done", response_model="claude-opus-4-6"),
    )
    assert asyncio.run(run_agent(tracer, agent, model, "find the GenAI conventions")) == "done"

    by_name = {s.name: s for s in tracer.finished}
    invoke = by_name.get("invoke_agent")
    assert invoke is not None and "gen_ai.agent.name" not in invoke.attributes, (
        "an unnamed agent's span is named invoke_agent"
    )
    search, fetch = by_name["tool_call search"], by_name["tool_call fetch"]
    assert [search.parent_span_id, fetch.parent_span_id] == [invoke.span_id] * 2, (
        "concurrent tool calls are children of the invoke_agent span"
    )
    assert search.end_ns < fetch.end_ns, "each span ends when its own call returns"
    chats = [s for s in tracer.finished if s.name == "chat"]
    assert [c.parent_span_id for c in chats] == [invoke.span_id] * 2, (
        "chat spans are siblings under the invoke_agent span"
    )

    assert built == ["create_agent"], "constructing an agent records one create_agent span"
    assert ops(tracer.finished).count("create_agent") == 1, "a run records invoke_agent, never create_agent"
    (created,) = [s for s in tracer.finished if s.attributes.get("gen_ai.operation.name") == "create_agent"]
    assert created.name == "create_agent" and "gen_ai.agent.name" not in created.attributes, (
        "an unnamed agent's create_agent span is named create_agent"
    )
    assert created.parent_span_id is None and created.attributes.get("gen_ai.provider.name") == "anthropic", (
        "an agent built outside any run gets a root create_agent span with its provider"
    )

    assert captured_content(chats[0], store) == {
        "gen_ai.input.messages": [{"role": "user", "content": "find the GenAI conventions"}],
        "gen_ai.output.messages": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"name": "search", "arguments": {"q": "search"}},
                    {"name": "fetch", "arguments": {"q": "fetch"}},
                ],
            }
        ],
    }, "content is stored in the store the tracer was given"
    attributes = json.dumps([s.attributes for s in tracer.finished])
    assert "GenAI conventions" not in attributes and "3 sources" not in attributes, (
        "spans carry references, never the content"
    )
    second = Tracer(capture_content=True, content_store=store, clock=FakeClock(), rng=random.Random(2))
    asyncio.run(run_agent(second, agent, scripted(ModelReply(text="hi")), "find the GenAI conventions"))
    assert "create_agent" not in ops(second.finished), "a run on another tracer records no create_agent either"
    assert (
        second.finished[0].attributes["gen_ai.input.messages.reference_id"]
        == chats[0].attributes["gen_ai.input.messages.reference_id"]
    ), "identical content shares one reference, across tracers"

    plain = Tracer(capture_content=True)
    with plain.span("chat") as span:
        plain.add_content(span, "gen_ai.input.messages", "hello")
    assert isinstance(span.start_ns, int) and isinstance(span.end_ns, int), (
        "timestamps are integer nanoseconds"
    )
    assert abs(span.start_ns - time.time_ns()) < 60 * 10**9, "timestamps are Unix-epoch nanoseconds"

    big = ExternalContentStore()
    start = time.perf_counter()
    refs = [big.put(f"turn {i}: tool result {i * 7919}") for i in range(18000)]
    assert time.perf_counter() - start < 0.15, "put stays fast as the store grows"
    assert len(set(refs)) == 18000 and big.put("turn 0: tool result 0") == refs[0], (
        "identical content shares one reference"
    )


@pytest.mark.skip("Part 2")
def test_content_store_roundtrip(tmp_path) -> None:
    """Captured content round-trips exactly through SQLite; spans carry only row ids."""
    path = str(tmp_path / "content.sqlite3")
    messages = [
        {"role": "system", "content": "Review the résumé. Answer in 中文 🚀"},
        {"role": "user", "content": "line one line two\x00end\ttab\r\n"},
        {"role": "assistant", "tool_calls": [{"name": "search", "arguments": {"z": 1, "a": [1.0, 2, True, None]}}]},
        {"role": "tool", "name": "search", "content": '{"hits": 3}'},
    ]
    store = SqliteContentStore(path)
    ref = store.put(messages)
    assert ref == "1", "a reference is the content row's id, as a decimal string"
    assert exact(store.get(ref), messages), "content comes back exactly as it went in"
    looks_like_json = '["not", "a", "list"]'
    text_ref = store.put(looks_like_json)
    assert exact(store.get(text_ref), looks_like_json), "a string comes back as the same string"
    assert store.put(messages) == ref, "identical content reuses its row"
    one, one_float, true = store.put([1]), store.put([1.0]), store.put([True])
    assert len({one, one_float, true}) == 3 and exact(store.get(one_float), [1.0]), (
        "1, 1.0 and True are different content"
    )
    store.close()

    reopened = SqliteContentStore(path)
    assert exact(reopened.get(ref), messages), "a reopened store resolves earlier references"
    assert reopened.put(looks_like_json) == text_ref, "identical content reuses its row after a reopen"
    erased = reopened.put("my SSN is 123-45-6789")
    reopened.delete(erased)
    with pytest.raises(KeyError):
        reopened.get(erased)
    with pytest.raises(KeyError):
        reopened.delete(erased)
    with pytest.raises(KeyError):
        reopened.get("no-such-ref")
    reopened.close()
    again = SqliteContentStore(path)
    with pytest.raises(KeyError):
        again.get(erased)
    assert erased not in {again.put("someone else's prompt"), again.put("my SSN is 123-45-6789")}, (
        "a deleted reference is never handed out again"
    )
    again.close()

    content = SqliteContentStore()
    tracer = Tracer(capture_content=True, content_store=content, clock=FakeClock(), rng=random.Random(3))
    agent = Agent("support_bot", "openai", "gpt-4o", tools={"lookup": tool("order 7 shipped")})
    model = scripted(ModelReply(tool_calls=calls("lookup")), ModelReply(text="It shipped."))
    asyncio.run(run_agent(tracer, agent, model, "where is order 7?"))
    lookup = next(s for s in tracer.finished if s.name == "tool_call lookup")
    assert lookup.attributes["gen_ai.tool.result.reference_id"].isdigit(), "spans carry row ids"
    assert captured_content(lookup, content) == {"gen_ai.tool.result": "order 7 shipped"}
    content.close()


@pytest.mark.skip("Part 3")
def test_tool_errors_by_model() -> None:
    """Tool errors are charged to the provider and model whose chat call requested the tool."""
    spans = [
        mk(10, None, "invoke_agent", 100, **{"gen_ai.provider.name": "anthropic", "gen_ai.request.model": "claude-opus-4-6"}),
        mk(11, 10, "chat", 110, **{"gen_ai.provider.name": "anthropic", "gen_ai.request.model": "claude-opus-4-6",
                                   "gen_ai.response.model": "claude-opus-4-6"}),
        mk(12, 10, "tool_call", 130, **{"gen_ai.tool.name": "search"}),
        mk(13, 10, "tool_call", 131, **{"gen_ai.tool.name": "fetch", "error.type": "TimeoutError"}),
        mk(14, 10, "chat", 200, **{"gen_ai.provider.name": "anthropic", "gen_ai.request.model": "claude-opus-4-6",
                                   "gen_ai.response.model": "claude-sonnet-4-5"}),
        mk(15, 10, "tool_call", 240, **{"gen_ai.tool.name": "search", "error.type": "RateLimitError"}),
        mk(20, None, "invoke_agent", 105, **{"gen_ai.provider.name": "openai", "gen_ai.request.model": "gpt-4o"}),
        mk(21, 20, "chat", 220, **{"gen_ai.request.model": "gpt-4o", "gen_ai.response.model": "gpt-4o-2024-08-06"}),
        mk(22, 20, "tool_call", 230, **{"gen_ai.tool.name": "search", "error.type": "ValueError"}),
        mk(23, 20, "tool_call", 250, **{"gen_ai.tool.name": "search"}),
        mk(30, 20, "chat", 300, **{"gen_ai.provider.name": "openai", "gen_ai.request.model": "gpt-4o",
                                   "gen_ai.response.model": "gpt-4o-mini"}),
        mk(31, 30, "tool_call", 310, **{"gen_ai.tool.name": "fetch", "error.type": "TimeoutError"}),
        mk(40, None, "tool_call", 400, **{"gen_ai.tool.name": "search", "error.type": "TimeoutError"}),
        mk(41, 999, "tool_call", 401, **{"gen_ai.tool.name": "search", "error.type": "TimeoutError"}),
        mk(42, 12, "tool_call", 132, **{"gen_ai.tool.name": "parse"}),
        mk(50, None, "invoke_agent", 450, **{"gen_ai.provider.name": "openai"}),
        mk(51, 50, "tool_call", 455, **{"gen_ai.tool.name": "search"}),
        mk(52, 50, "chat", 460, **{"gen_ai.request.model": "gpt-4o"}),
        mk(62, None, "invoke_agent", 490, **{"gen_ai.provider.name": "aws.bedrock"}),
        mk(61, 62, "chat", 500, **{"gen_ai.request.model": "amazon.nova-pro-v1:0"}),
        mk(60, 62, "chat", 500, **{"gen_ai.request.model": "amazon.nova-lite-v1:0"}),
        mk(63, 62, "tool_call", 500, **{"gen_ai.tool.name": "kb_lookup"}),
    ]
    random.Random(3).shuffle(spans)
    report = tool_errors(spans)
    rows = {(r.provider, r.model, r.tool): (r.calls, r.errors) for r in report.rows}

    assert sum(c for (p, _, _), (c, _) in rows.items() if p == "anthropic") == 3, (
        "a tool span is matched to a chat span of its own agent run"
    )
    assert rows.get(("anthropic", "claude-sonnet-4-5", "search")) == (1, 1), (
        "tool calls are charged to the model that answered (gen_ai.response.model)"
    )
    assert not any(p == "unknown" for p, _, _ in rows), (
        "a chat span without gen_ai.provider.name takes its agent's provider"
    )
    assert rows.get(("openai", "gpt-4o-mini", "fetch")) == (1, 1), "a tool span under a chat span belongs to it"
    assert rows.get(("aws.bedrock", "amazon.nova-lite-v1:0", "kb_lookup")) == (1, 0), (
        "the latest chat span at or before the tool call; ties go to the smaller span_id"
    )
    assert report.orphaned == 4, "orphaned tool spans are counted apart"
    assert report.rows == [
        ToolErrorRow("anthropic", "claude-opus-4-6", "fetch", 1, 1),
        ToolErrorRow("anthropic", "claude-opus-4-6", "search", 1, 0),
        ToolErrorRow("anthropic", "claude-sonnet-4-5", "search", 1, 1),
        ToolErrorRow("aws.bedrock", "amazon.nova-lite-v1:0", "kb_lookup", 1, 0),
        ToolErrorRow("openai", "gpt-4o-2024-08-06", "search", 2, 1),
        ToolErrorRow("openai", "gpt-4o-mini", "fetch", 1, 1),
    ], "rows sorted by (provider, model, tool)"
    assert tool_errors(spans[::-1]) == report, "the report does not depend on the order spans arrive in"

    routed = [
        mk(70, None, "invoke_agent", 600, **{"gen_ai.provider.name": "openai", "gen_ai.request.model": "gpt-4o"}),
        mk(71, 70, "chat", 610, **{"gen_ai.provider.name": "aws.bedrock",
                                   "gen_ai.request.model": "amazon.nova-lite-v1:0"}),
        mk(72, 70, "tool_call", 620, **{"gen_ai.tool.name": "search"}),
    ]
    assert tool_errors(routed).rows == [ToolErrorRow("aws.bedrock", "amazon.nova-lite-v1:0", "search", 1, 0)], (
        "a chat span's own gen_ai.provider.name comes before its agent's"
    )

    tracer = Tracer(clock=FakeClock(), rng=random.Random(4))
    agent = Agent("triage", "anthropic", "claude-opus-4-6",
                  tools={"lookup": tool("", fail=TimeoutError("upstream")), "notes": tool("none")})
    model = scripted(
        ModelReply(tool_calls=calls("lookup", "notes"), response_model="claude-opus-4-6-fast"),
        ModelReply(tool_calls=calls("lookup")),
        ModelReply(text="escalating"),
    )
    asyncio.run(run_agent(tracer, agent, model, "ticket 41"))
    assert tool_errors(tracer.finished) == ToolErrorReport(
        [
            ToolErrorRow("anthropic", "claude-opus-4-6", "lookup", 1, 1),
            ToolErrorRow("anthropic", "claude-opus-4-6-fast", "lookup", 1, 1),
            ToolErrorRow("anthropic", "claude-opus-4-6-fast", "notes", 1, 0),
        ],
        0,
    ), "a traced run, from its span attributes alone"


@pytest.mark.skip("Part 4")
def test_span_feed() -> None:
    """Concurrent agent runs stream one NDJSON line per span, each as soon as the span ends."""
    tracer = Tracer(clock=FakeClock(), rng=random.Random(0))
    lines: list[str] = []

    async def two_agents() -> None:
        gate = asyncio.Event()

        async def waits(arguments):
            await gate.wait()
            return "ok"

        alpha = Agent("alpha", "anthropic", "claude-opus-4-6", tools={"wait": waits, "lookup": tool("l")})
        beta = Agent("beta", "openai", "gpt-4o", tools={"quick": tool("q", yields=2)})
        both = asyncio.gather(
            run_agent(tracer, alpha, scripted(ModelReply(tool_calls=calls("wait", "lookup")), ModelReply(text="a")), "a"),
            run_agent(tracer, beta, scripted(ModelReply(tool_calls=calls("quick")), ModelReply(text="b")), "b"),
        )
        async for line in stream_spans(tracer, both):
            lines.append(line)
            gate.set()

    run(two_agents())
    assert all(line.endswith("\n") and line.count("\n") == 1 for line in lines), "one JSON object per line"
    records = [json.loads(line) for line in "".join(lines).splitlines()]
    assert len(records) == len(tracer.finished) == 9, "one line per span, none lost at the end"
    assert all(
        re.fullmatch(r"[0-9a-f]{32}", r["trace_id"]) and re.fullmatch(r"[0-9a-f]{16}", r["span_id"])
        for r in records
    ), "ids are zero-padded lowercase hex"
    assert [r["span_id"] for r in records] == [f"{s.span_id:016x}" for s in tracer.finished], (
        "lines come in the order spans end"
    )
    by_id = {r["span_id"]: r for r in records}
    roots = [r["name"] for r in records if r["parent_span_id"] is None]
    assert sorted(roots) == ["invoke_agent alpha", "invoke_agent beta"], "a root's parent_span_id is null"
    owners = {
        r["attributes"]["gen_ai.tool.name"]: by_id[r["parent_span_id"]]["name"]
        for r in records
        if r["name"].startswith("tool_call")
    }
    assert owners == {"wait": "invoke_agent alpha", "lookup": "invoke_agent alpha", "quick": "invoke_agent beta"}, (
        "each tool span's parent is its own agent's span"
    )
    first = tracer.finished[0]
    assert records[0]["start_ns"] == first.start_ns and type(records[0]["start_ns"]) is int, (
        "timestamps are the integer epoch nanoseconds"
    )
    assert records[0]["attributes"] == first.attributes
    assert tracer.processors == [], "the feed detaches from the tracer when it stops"

    class ModelDown(Exception):
        pass

    async def broken(messages):
        raise ModelDown("503")

    failing = Tracer(clock=FakeClock(), rng=random.Random(34))
    got: list[dict] = []

    async def failed_run() -> None:
        with pytest.raises(ModelDown):
            agent = Agent("gamma", "anthropic", "claude-opus-4-6")
            async for line in stream_spans(failing, run_agent(failing, agent, broken, "x")):
                got.append(json.loads(line))

    run(failed_run())
    assert [(r["name"], r["attributes"].get("error.type")) for r in got] == [
        ("chat", "ModelDown"),
        ("invoke_agent gamma", "ModelDown"),
    ], "a failed run streams all of its spans, then raises its error"
    assert {r["trace_id"] for r in got} == {f"{failing.trace_id:032x}"}, "ids are zero-padded lowercase hex"
    assert failing.processors == [], "the feed detaches from the tracer when it stops"

    closing = Tracer(clock=FakeClock(), rng=random.Random(6))
    cancelled: list[str] = []
    started: list[asyncio.Event] = []

    async def hangs(arguments):
        started[0].set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append("hang")
            raise
        return "never"

    async def close_early() -> tuple[dict, list[str], list[str | None]]:
        started.append(asyncio.Event())
        agent = Agent("delta", "anthropic", "claude-opus-4-6", tools={"hang": hangs})
        feed = stream_spans(closing, run_agent(closing, agent, scripted(ModelReply(tool_calls=calls("hang"))), "x"))
        first_line = json.loads(await feed.__anext__())
        await started[0].wait()
        await feed.aclose()
        return first_line, list(cancelled), [s.attributes.get("error.type") for s in closing.finished]

    first_line, cancelled_by_close, errors_by_close = run(close_early())
    assert first_line["name"] == "chat"
    assert cancelled_by_close == ["hang"], "closing the feed cancels the run and waits for it"
    assert errors_by_close == [None, "CancelledError", "CancelledError"], (
        "closing the feed cancels the run and waits for it"
    )
    assert closing.processors == [], "the feed detaches from the tracer when it stops"


@pytest.mark.skip("Part 5")
def test_agent_usage_rollup() -> None:
    """Token usage rolls up through agents that call agents."""

    def chat(span_id, parent, start, tokens=None):
        attrs = {}
        if tokens:
            attrs = {"gen_ai.usage.input_tokens": tokens[0], "gen_ai.usage.output_tokens": tokens[1]}
        return mk(span_id, parent, "chat", start, **attrs)

    def agent(span_id, parent, start, name):
        return mk(span_id, parent, "invoke_agent", start, **{"gen_ai.agent.name": name})

    spans = [
        agent(1, None, 10, "planner"),
        chat(2, 1, 11, (100, 10)),
        mk(3, 1, "tool_call", 30),
        agent(4, 3, 31, "researcher"),
        chat(5, 4, 32, (50, 5)),
        mk(6, 4, "tool_call", 39),
        agent(7, 6, 40, "researcher"),
        chat(8, 7, 41, (7, 1)),
        mk(9, 1, "tool_call", 50),
        agent(10, 9, 51, "writer"),
        chat(11, 10, 52, (20, 4)),
        chat(12, 10, 53),
        chat(13, 9, 60, (30, 6)),
        agent(20, None, 5, "planner"),
        chat(21, 20, 6, (1, 1)),
        chat(30, 999, 70, (9, 9)),
        chat(31, None, 71, (2, 0)),
        agent(40, 998, 80, "auditor"),
        chat(41, 40, 81, (3, 3)),
    ]
    random.Random(5).shuffle(spans)
    runs, unattributed = agent_usage(spans)
    by_id = {r.span_id: r for r in runs}

    assert sum(r.agent == "researcher" for r in runs) == 2, "two runs with the same name are two runs"
    assert 40 in by_id, "a run whose parent never arrived is a root of its own"
    assert by_id[1].own == Usage(130, 16), "own usage counts the run's own chat spans only, through its tool calls"
    assert by_id[1].total == Usage(207, 26), "total adds every agent run nested below, through tool calls"
    assert [by_id[i].depth for i in (1, 4, 7, 10)] == [0, 1, 2, 1], "depth counts the agent runs above"
    assert unattributed == Usage(11, 9), "chat spans outside any agent run are unattributed"
    assert runs == [
        AgentUsage(20, "planner", 0, Usage(1, 1), Usage(1, 1)),
        AgentUsage(1, "planner", 0, Usage(130, 16), Usage(207, 26)),
        AgentUsage(4, "researcher", 1, Usage(50, 5), Usage(57, 6)),
        AgentUsage(7, "researcher", 2, Usage(7, 1), Usage(7, 1)),
        AgentUsage(10, "writer", 1, Usage(20, 4), Usage(20, 4)),
        AgentUsage(40, "auditor", 0, Usage(3, 3), Usage(3, 3)),
    ], "runs in pre-order, siblings by start time"

    tracer = Tracer(clock=FakeClock(), rng=random.Random(7))
    researcher = Agent("researcher", "anthropic", "claude-sonnet-4-5", tools={"search": tool("3 hits")})
    research_model = scripted(
        ModelReply(tool_calls=calls("search"), input_tokens=40, output_tokens=8),
        ModelReply(text="notes", input_tokens=60, output_tokens=20),
    )
    lead = Agent("lead", "anthropic", "claude-opus-4-6",
                 tools={"research": agent_tool(tracer, researcher, research_model)})
    lead_model = scripted(
        ModelReply(tool_calls=(ToolCall("research", {"task": "otel"}),), input_tokens=100, output_tokens=10),
        ModelReply(text="report", input_tokens=300, output_tokens=50),
    )
    asyncio.run(run_agent(tracer, lead, lead_model, "write the report"))
    traced, none = agent_usage(tracer.finished)
    assert [(r.agent, r.depth, r.own, r.total) for r in traced] == [
        ("lead", 0, Usage(400, 60), Usage(500, 88)),
        ("researcher", 1, Usage(100, 28), Usage(100, 28)),
    ], "a traced run with a sub-agent"
    assert none == Usage()
