import asyncio
import json
import re
import time
from fractions import Fraction

import pytest
from agnomastra.agno import AgentSpec, AgnoApp, SessionStore, Tool
from agnomastra.capacity import Stage, latency_saving, parse_duration, plan
from agnomastra.mastra import MastraAgent, MastraTool, Workflow
from agnomastra.schemas import Flow, Step, check_flow, first_mismatch
from agnomastra.server import StreamingBackend
from agnomastra.storage import CompositeStorage, Event, Message, Snapshot


def typed(value):
    """value with every scalar tagged by its type and dict key order kept, for exact comparisons."""
    if isinstance(value, dict):
        return ("dict", [(k, typed(v)) for k, v in value.items()])
    if isinstance(value, list):
        return ("list", [typed(v) for v in value])
    if isinstance(value, float):
        return ("float", value.hex())
    return (type(value).__name__, value)


def is_json(data: bytes) -> bool:
    """True when data is one JSON document."""
    try:
        json.loads(data)
    except ValueError:
        return False
    return True


def registry(n: int) -> list[Tool]:
    """An app's tool catalogue: n tools, each with a small parameter schema."""
    return [
        Tool(f"tool_{i}", f"Tool number {i}", {"query": "string", "limit": "number"}, lambda **kw: "ok")
        for i in range(n)
    ]


@pytest.mark.skip("Part 1")
def test_runtime_handlers() -> None:
    """Agno-shaped requests stay isolated and cheap; Mastra-shaped tools and workflows keep honest traces."""
    seen = []

    def model(agent) -> str:
        seen.append((agent, list(agent.memory)))
        return f"reply {len(seen)}"

    app = AgnoApp(AgentSpec("support", ["system: be brief"]), registry(3), model)
    app.handle("s1", "my name is Ada")
    app.handle("s2", "what is my name?")
    app.handle("s1", "and now?")
    assert [memory for _, memory in seen] == [
        ["system: be brief", "user: my name is Ada"],
        ["system: be brief", "user: what is my name?"],
        ["system: be brief", "user: my name is Ada", "assistant: reply 1", "user: and now?"],
    ], "a request sees its own session's history and nothing else"
    assert len({id(agent) for agent, _ in seen}) == 3, "every request runs on a fresh agent"

    def search(query: str, limit: int) -> str:
        return f"{limit} results for {query.lower()}"

    agent = MastraAgent("research", "search, summarise, cite", [
        MastraTool("search", "Web search over a fixture corpus", {"query": "string", "limit": "number"}, search),
    ])
    output, trace = agent.run("research agent engineering", [
        ("search", {"query": "Agent Engineering", "limit": 3}),
        ("search", {"query": 42, "limit": 3}),
        ("lookup", {"query": "x"}),
        ("search", {}),
        ("search", {"query": "BFCL V4", "limit": 0}),
    ])
    assert output == "research processed 5 tools"
    assert trace == [
        ("search", "3 results for agent engineering"),
        ("search", "error: field query: expected string, got number"),
        ("lookup", "error: unknown tool"),
        ("search", "error: missing field query"),
        ("search", "0 results for bfcl v4"),
    ], "a call that breaks the input schema is recorded, not executed"
    _, trace = agent.run("research agent engineering", [
        ("search", {"limit": "ten"}),
        ("search", {"query": 7}),
    ])
    assert trace == [
        ("search", "error: missing field query"),
        ("search", "error: field query: expected string, got number"),
    ], "the first problem in the schema's order is reported"
    _, trace = agent.run("research agent engineering", [
        ("search", {"query": None, "limit": 3}),
        ("search", {"query": "BFCL V4", "limit": True}),
    ])
    assert trace == [
        ("search", "error: field query: expected string, got null"),
        ("search", "error: field limit: expected number, got boolean"),
    ], "None is a null value, not a missing field, and True is not a number"

    def normalize(p: dict) -> dict:
        p["query"] = p["query"].strip().lower()
        return p

    def tag(p: dict) -> dict:
        p["tags"].append("agents")
        return p

    def rank(p: dict) -> dict:
        p["meta"]["ranked"] = True
        p["tags"].append("ranked")
        return p

    flow = Workflow([("normalize", normalize), ("tag", tag), ("rank", rank)])
    steps = flow.run({"query": "  Agent Engineering 2026 ", "tags": [], "meta": {"ranked": False}})
    q = "agent engineering 2026"
    assert steps == [
        ("normalize", {"query": q, "tags": [], "meta": {"ranked": False}}),
        ("tag", {"query": q, "tags": ["agents"], "meta": {"ranked": False}}),
        ("rank", {"query": q, "tags": ["agents", "ranked"], "meta": {"ranked": True}}),
    ], "each trace entry keeps its step's output as it was when the step returned"

    big = AgnoApp(AgentSpec("support", ["system: be brief"]), registry(1000), lambda agent: "ok")
    start = time.perf_counter()
    for i in range(300):
        big.handle(f"user-{i % 50}", "hi")
    assert time.perf_counter() - start < 0.05, "creating an agent should not cost more with a bigger tool registry"
    assert len({id(agent.tools) for agent, _ in seen}) == 1, "agents share the app's registry instead of copying it"


@pytest.mark.skip("Part 2")
def test_composite_storage(tmp_path) -> None:
    """Memory, workflow snapshots and events each go to their own backend and read back exactly."""
    store = CompositeStorage(tmp_path)
    store.add_message(Message("r1", "user", "Grüße,\r\nsecond line\n"))
    store.add_message(Message("r2", "user", "other session"))
    store.add_message(Message("r1", "assistant", "Hallo!"))
    state = {
        "z_last": None,
        "outputs": {"fetch": {"status": 200, "latency_us": 2.0, "cached": True}},
        "a_first": [0.1 + 0.2, 2**64 + 1, -0.0, "naïve"],
    }
    backfill = "backfill/" + ",".join(f"2026-10-{day:02d}" for day in range(1, 32))
    runs = {
        "r1": Snapshot("r1", "running", "fetch", state),
        "nightly/2026-11-02": Snapshot("nightly/2026-11-02", "suspended", "approve", {"n": 1}),
        "nightly_2026-11-02": Snapshot("nightly_2026-11-02", "failed", "fetch", {"n": 2}),
        "nightly-7": Snapshot("nightly-7", "running", "fetch", {"n": 3}),
        "../escape": Snapshot("../escape", "running", "fetch", {"n": 4}),
        backfill: Snapshot(backfill, "running", "fetch", {"n": 5}),
    }
    store.save_snapshot(Snapshot("r1", "running", "plan", {}))
    for snapshot in runs.values():
        store.save_snapshot(snapshot)
    with pytest.raises(ValueError):
        store.save_snapshot(Snapshot("", "running", "fetch", {}))
    first = Event("r1", "agent.run", 1_767_225_600_123_456_789, {"note": "line sep", "who": "Grüße"})
    second = Event("t2", "tool.call", 1_767_225_600_123_456_790, {"tool": "search", "ok": False})
    store.record(first)
    store.record(second)
    store.close()

    reopened = CompositeStorage(tmp_path)
    assert reopened.messages("r1") == [
        Message("r1", "user", "Grüße,\r\nsecond line\n"),
        Message("r1", "assistant", "Hallo!"),
    ], "a session's messages read back exactly, in order"
    for run_id, snapshot in runs.items():
        loaded = reopened.load_snapshot(run_id)
        assert loaded.run_id == run_id, "every run id keeps its own snapshot"
        assert typed(loaded.__dict__) == typed(snapshot.__dict__), "a snapshot round-trips exactly"
    assert reopened.runs() == sorted(runs), "runs() lists run ids in sorted order"
    with pytest.raises(KeyError):
        reopened.load_snapshot("never-ran")

    third = Event("r1", "agent.end", 1_767_225_600_123_456_791, {})
    reopened.record(third)
    events = reopened.events()
    assert [typed(e.__dict__) for e in events] == [typed(e.__dict__) for e in (first, second, third)], (
        "a reopened store keeps every record, and events read back exactly in order"
    )
    assert reopened.events("r1") == [first, third], "filter events by trace"
    reopened.close()

    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert [f for f in files if not f.startswith("workflows/")] == ["memory.sqlite3", "observability.log"], (
        "each record type has its own backend, and snapshots stay inside workflows/"
    )
    assert len(files) == 2 + len(runs), "one snapshot file per run id"
    assert all(is_json((tmp_path / f).read_bytes()) for f in files if f.startswith("workflows/")), (
        "every snapshot file is a JSON document"
    )
    assert (tmp_path / "memory.sqlite3").read_bytes().startswith(b"SQLite format 3\x00")
    log = (tmp_path / "observability.log").read_bytes()
    assert "Grüße".encode() in log, "the log is readable UTF-8 text"
    lines = log.split(b"\n")
    assert lines[-1] == b"" and len(lines) == 4, "one JSON object per line"
    assert [json.loads(line)["name"] for line in lines[:-1]] == ["agent.run", "tool.call", "agent.end"]


STAGES = [
    Stage("instantiate", "40ms", 64),
    Stage("model", "1.8s", 64),
    Stage("tools", "120ms", 32),
    Stage("persist", "6ms", 8),
]


@pytest.mark.skip("Part 3")
def test_capacity_plan() -> None:
    """Little's law per stage: find the bottleneck, and see what a faster runtime would buy."""
    assert [parse_duration(t) for t in ("750ns", "2us", "2\u03bcs", "2\u00b5s", "40ms", "1.8s")] == [
        750, 2_000, 2_000, 2_000, 40_000_000, 1_800_000_000,
    ], "durations in ns, us, \u03bcs, \u00b5s, ms and s"
    assert parse_duration("2.05s") == 2_050_000_000, "durations parse to exact nanoseconds"
    for bad in ("5m", "1.5ns", "-2ms", "+2ms", "2 ms", "ms", "2s "):
        with pytest.raises(ValueError):
            parse_duration(bad)

    p = plan(30, STAGES)
    assert [(load.name, load.in_flight, load.workers_needed) for load in p.loads] == [
        ("instantiate", Fraction(6, 5), 2),
        ("model", Fraction(54), 55),
        ("tools", Fraction(18, 5), 4),
        ("persist", Fraction(9, 50), 1),
    ], "in_flight = rate x service time; workers_needed keeps utilization below 1"
    assert p.loads[2].utilization == Fraction(9, 80), "every number in the plan is exact"
    assert (p.bottleneck, p.sustainable, p.max_rate, p.latency_ns) == ("model", True, Fraction(320, 9), 1_966_000_000)

    full = plan(30, [Stage("route", "2ms", 1), Stage("model", "100ms", 3)])
    assert full.loads[1].utilization == 1 and not full.sustainable, (
        "a stage at exactly 100% utilization cannot keep up"
    )
    assert full.loads[1].workers_needed == 4, "workers_needed keeps utilization below 1"
    fan_in = plan(2000, [Stage("instantiate", "1ms", 1), Stage("model", "50ms", 200)])
    assert (fan_in.bottleneck, fan_in.sustainable, fan_in.max_rate) == ("instantiate", False, 1000), (
        "the bottleneck is the busiest stage, not the slowest one"
    )

    tie = plan(5, [Stage("a", "100ms", 1), Stage("b", "300ms", 3), Stage("c", "50ms", 1)])
    assert tie.bottleneck == "b", "a tie goes to the longer service time"
    tie = plan(5, [Stage("x", "100ms", 2), Stage("y", "100ms", 2)])
    assert tie.bottleneck == "x", "then to the earlier stage"
    for bad in ([], [Stage("a", "1ms", 1), Stage("a", "2ms", 1)], [Stage("a", "1ms", 0)], [Stage("a", "0ms", 1)]):
        with pytest.raises(ValueError):
            plan(1, bad)
    with pytest.raises(ValueError):
        plan(-1, STAGES)
    idle = plan(0, STAGES)
    assert (idle.sustainable, idle.max_rate) == (True, Fraction(320, 9)), (
        "max_rate depends on the stages, not on the rate"
    )

    saved = latency_saving(STAGES, "instantiate", "2\u03bcs")
    assert saved == Fraction(40_000_000 - 2_000, 1_966_000_000), "the share of end-to-end time saved"
    assert 0.02 < saved < 0.021
    assert latency_saving(STAGES, "model", "2.7s") < 0, "a slower stage saves a negative share"
    with pytest.raises(KeyError):
        latency_saving(STAGES, "gpu", "1ms")


def parse_chunked(raw: bytes) -> tuple[list[str], list[bytes]]:
    """Split a raw HTTP/1.1 response into header lines and the data of each chunk."""
    head, sep, body = raw.partition(b"\r\n\r\n")
    assert sep, "the headers end with an empty line"
    chunks = []
    while True:
        size, sep, body = body.partition(b"\r\n")
        assert sep, "each chunk size line ends with CRLF"
        assert re.fullmatch(rb"[0-9A-Fa-f]+", size), "the chunk size is hex digits only"
        n = int(size, 16)
        if n == 0:
            assert body == b"\r\n", "the last chunk is 0 CRLF CRLF and nothing follows"
            return head.decode().split("\r\n"), chunks
        data, body = body[:n], body[n:]
        assert body.startswith(b"\r\n"), "chunk data is followed by CRLF"
        chunks.append(data)
        body = body[2:]


async def consume(response, sink: list[bytes]) -> None:
    async for piece in response:
        sink.append(piece)


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


async def within(awaitable, message: str):
    try:
        return await asyncio.wait_for(awaitable, 0.5)
    except asyncio.TimeoutError:
        pass
    pytest.fail(message)


@pytest.mark.skip("Part 4")
def test_streaming_backend() -> None:
    """Responses stream as HTTP/1.1 chunks; one session runs one request at a time."""
    tokens = ["Hel", "lo,", " ", "", "Grüße ", "\U0001f680", " 0123456789abcdef"]

    async def words(messages):
        for token in tokens:
            await asyncio.sleep(0)
            yield token

    async def plain() -> None:
        store = SessionStore()
        out: list[bytes] = []
        await within(consume(StreamingBackend(store, words).handle("s0", "hi"), out), "the response completes")
        head, chunks = parse_chunked(b"".join(out))
        assert head[0] == "HTTP/1.1 200 OK"
        assert "transfer-encoding: chunked" in [line.lower() for line in head]
        assert not any(line.lower().startswith("content-length") for line in head)
        assert chunks == [t.encode() for t in tokens if t], "one chunk per non-empty token"
        assert store.history("s0") == ["user: hi", f"assistant: {''.join(tokens)}"]

    asyncio.run(plain())

    async def sessions() -> None:
        store = SessionStore()
        calls: list[tuple[str, list[str]]] = []
        release = {p: asyncio.Event() for p in ("first", "second", "other", "bye", "again")}

        async def gated(messages):
            prompt = messages[-1].removeprefix("user: ")
            calls.append((prompt, messages))
            yield f"echo:{prompt}"
            await release[prompt].wait()
            yield " done"

        backend = StreamingBackend(store, gated)
        out: dict[str, list[bytes]] = {"first": [], "second": [], "other": []}
        first = asyncio.create_task(consume(backend.handle("s1", "first"), out["first"]))
        second = asyncio.create_task(consume(backend.handle("s1", "second"), out["second"]))
        other = asyncio.create_task(consume(backend.handle("s2", "other"), out["other"]))
        await settle()
        started = [p for p, _ in calls]
        assert "other" in started, "different sessions run in parallel"
        assert started[0] == "first" and "second" not in started, "requests in one session run one at a time"
        assert b"\r\necho:first\r\n" in b"".join(out["first"]), "the first chunk goes out before the model finishes"

        release["other"].set()
        await within(other, "different sessions run in parallel")
        release["first"].set()
        await within(first, "the response completes")
        await settle()
        assert calls[-1] == ("second", ["user: first", "assistant: echo:first done", "user: second"]), (
            "a queued request sees the turn before it"
        )
        release["second"].set()
        await within(second, "the response completes")
        for prompt in out:
            assert parse_chunked(b"".join(out[prompt]))[1] == [f"echo:{prompt}".encode(), b" done"]

        abandoned = backend.handle("s3", "bye")
        seen = b""
        while b"\r\necho:bye\r\n" not in seen:
            seen += await within(abandoned.__anext__(), "the first chunk goes out before the model finishes")
        await abandoned.aclose()
        release["again"].set()
        again = backend.handle("s3", "again")
        seen = b""
        while not seen.endswith(b"\r\n0\r\n\r\n"):
            seen += await within(again.__anext__(), "an abandoned response frees its session")
        await again.aclose()
        assert "user: bye" not in store.history("s3"), "an abandoned response stores no turn"
        assert store.history("s3") == ["user: again", "assistant: echo:again done"], (
            "the turn is stored by the time the last chunk goes out"
        )

    asyncio.run(sessions())


def obj(fields: dict, strict: bool = False) -> dict:
    return {"object": fields, "strict": True} if strict else {"object": fields}


ITEM = obj({"sku": "string", "price": "number"})


@pytest.mark.skip("Part 5")
def test_flow_schemas() -> None:
    """A workflow type-checks when every step's output fits the next step's input, through any nesting."""
    assert first_mismatch("integer", "number") is None, "an integer fits a number"
    m = first_mismatch("number", "integer")
    assert m is not None and m.path == "$", "a number is not always an integer"
    assert first_mismatch("boolean", "number") is not None
    assert first_mismatch("string", {"optional": "string"}) is None
    assert first_mismatch({"optional": "string"}, "string") is not None, "an optional value may be missing"
    assert first_mismatch({"union": ["string", "integer"]}, {"union": ["integer", "string"]}) is None, (
        "a union fits a union that accepts each of its members"
    )
    assert first_mismatch({"union": ["string", "integer"]}, "string") is not None, (
        "every member of a union must fit"
    )
    assert first_mismatch("integer", {"union": ["string", "number"]}) is None

    src = obj({"order": obj({"items": {"array": obj({"sku": "string", "price": "integer", "note": "string"})}})})
    assert first_mismatch(src, obj({"order": obj({"items": {"array": ITEM}})})) is None, (
        "extra fields are fine unless the object is strict"
    )
    wrong = obj({"order": obj({"items": {"array": obj({"sku": "string", "price": "string"})}})})
    m = first_mismatch(wrong, obj({"order": obj({"items": {"array": ITEM}})}))
    assert m is not None and m.path == "$.order.items[].price", "report the path of the first mismatch"
    m = first_mismatch(src, obj({"order": obj({"items": {"array": obj({"sku": "string"}, strict=True)}})}))
    assert m is not None and m.path == "$.order.items[].price", "a strict object rejects extra fields"
    m = first_mismatch(
        obj({"id": "string", "draft": {"optional": "boolean"}}),
        obj({"id": "string", "draft": "boolean", "tags": {"optional": {"array": "string"}}}),
    )
    assert m is not None and m.path == "$.draft", "a required field cannot come from an optional one"
    m = first_mismatch(obj({"id": "string"}), obj({"id": "string", "tags": {"optional": {"array": "string"}}}))
    assert m is None, "an optional field may be left out"
    m = first_mismatch(obj({"n": "string", "id": "integer"}), obj({"id": "string", "n": "number"}))
    assert m is not None and m.path == "$.id", "fields are checked in the consumer's order"

    fetch = Step("fetch", obj({"url": "string"}), obj({"items": {"array": ITEM}, "next": {"optional": "string"}}))
    score = Step("score", obj({"items": {"array": ITEM}}), obj({"items": {"array": ITEM}, "score": "number"}))
    publish = Step("publish", obj({"score": "number"}), obj({"ok": "boolean"}))
    good = Flow("pipeline", [fetch, Flow("enrich", [Flow("inner", [score])]), publish])
    assert check_flow(good) is None, "a nested flow takes its first step's input and gives its last step's output"
    rescore = Flow("rescore", [score])
    assert check_flow(Flow("pipeline", [fetch, rescore, rescore, publish])) is None, (
        "a flow may be used twice; only a flow inside itself is an error"
    )

    strict_publish = Step("publish", obj({"score": "number"}, strict=True), obj({"ok": "boolean"}))
    bad_inside = Step("audit", obj({"items": {"array": ITEM}, "score": "integer"}), obj({"ok": "boolean"}))
    nested = Flow("enrich", [score, bad_inside])
    broken = Flow("pipeline", [fetch, Flow("outer", [nested]), strict_publish])
    found = check_flow(broken)
    assert found is not None
    assert (found.producer, found.consumer) == ("pipeline/outer/enrich/score", "pipeline/outer/enrich/audit"), (
        "links are checked in the order data crosses them, with qualified step names"
    )
    assert found.mismatch.path == "$.score"
    load = Step("load", obj({"path": "string"}), obj({"rows": {"array": ITEM}}))
    found = check_flow(Flow("pipeline", [load, nested]))
    assert found is not None
    assert (found.producer, found.consumer, found.mismatch.path) == (
        "pipeline/load", "pipeline/enrich/score", "$.items",
    ), "the link into a nested flow comes before the links inside it"
    ranked = obj({"score": "number", "rank": "integer"})
    rank = Step("rank", obj({"items": {"array": ITEM}, "score": "number"}), ranked)
    found = check_flow(Flow("pipeline", [fetch, Flow("outer", [Flow("enrich", [score, rank])]), strict_publish]))
    assert found is not None
    assert (found.producer, found.consumer, found.mismatch.path) == (
        "pipeline/outer/enrich/rank", "pipeline/publish", "$.rank",
    ), "the link out of a nested flow starts at its last step"
    for empty in (Flow("empty", []), Flow("pipeline", [fetch, Flow("later", [])])):
        with pytest.raises(ValueError):
            check_flow(empty)
    loop = Flow("loop", [fetch])
    loop.steps.append(loop)
    with pytest.raises(ValueError):
        check_flow(loop)
