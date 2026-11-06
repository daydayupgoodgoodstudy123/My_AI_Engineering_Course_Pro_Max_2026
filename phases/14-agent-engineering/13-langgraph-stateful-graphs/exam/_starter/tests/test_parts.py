import asyncio
import datetime
import json
import random
import time

import pytest
from stategraph.checkpoint import InMemoryCheckpointer, Record
from stategraph.effects import ReplayMismatch, World
from stategraph.graph import END, HUMAN, PAUSE, START, GraphError, StateGraph, append
from stategraph.runner import Checkpoint, PausedAtNode, Runner
from stategraph.sqlite_store import SQLiteCheckpointer, dumps, loads
from stategraph.stream import stream_updates


class Desk:
    """The support desk's ticket system: open() files a new ticket, send() mails one out."""

    def __init__(self) -> None:
        self.tickets: list[str] = []
        self.sent: list[str] = []
        self.relay_down = 0  # the next relay_down sends fail

    def open(self, kind: str) -> str:
        self.tickets.append(f"{kind}-{len(self.tickets) + 1}")
        return self.tickets[-1]

    def send(self, ticket: str) -> str:
        if self.relay_down:
            self.relay_down -= 1
            raise ConnectionError("mail relay unavailable")
        self.sent.append(ticket)
        return f"sent {ticket}"


def route_by_keywords(state) -> str:
    """The lesson's classifier: refund words, then bug words; everything else is sales."""
    text = state["input"].lower()
    if "refund" in text or "money back" in text:
        return "refund"
    if "crash" in text or "bug" in text or "error" in text:
        return "bug"
    return "sales"


def support_graph(desk: Desk, router=None) -> StateGraph:
    """classify -> refund | bug -> human_gate -> send, and sales -> send: a quote needs no approval."""

    def gate(state, ctx):
        return {} if state.get("approved") else {PAUSE: "awaiting approval"}

    graph = StateGraph()
    graph.add_node("classify", lambda state, ctx: {"route": route_by_keywords(state)})
    for name, kind in (("refund", "REF"), ("bug", "BUG"), ("sales", "SAL")):
        graph.add_node(name, lambda state, ctx, kind=kind: {"ticket": desk.open(kind)})
    graph.add_node("human_gate", gate)
    graph.add_node("send", lambda state, ctx: {"output": desk.send(state["ticket"])})
    graph.set_entry("classify")
    graph.add_conditional_edges(
        "classify", router or (lambda state: state["route"]), {"refund": "refund", "bug": "bug", "sales": "sales"}
    )
    graph.add_edge("refund", "human_gate")
    graph.add_edge("bug", "human_gate")
    graph.add_conditional_edges(
        "human_gate", lambda state: "go" if state.get("approved") else "wait", {"go": "send", "wait": "human_gate"}
    )
    graph.add_edge("sales", "send")
    graph.add_edge("send", END)
    return graph


class ScriptedRouter:
    """An LLM router stand-in: every call gives the next scripted label, so asking twice can change the answer."""

    def __init__(self, labels: list) -> None:
        self.labels = labels
        self.calls = 0

    def __call__(self, state) -> str:
        self.calls += 1
        return self.labels[(self.calls - 1) % len(self.labels)]


class Notebook:
    """A tool node that hands back the very list it keeps its pages in."""

    def __init__(self) -> None:
        self.pages: list[int] = []

    def __call__(self, state, ctx):
        self.pages.append(len(self.pages) + 1)
        return {"pages": self.pages}


def steps(history: list[Checkpoint]) -> list[tuple]:
    return [(c.step, c.node) for c in history]


@pytest.mark.skip("Part 1")
def test_pause_and_resume() -> None:
    """A run pauses at the gate, resumes after its latest checkpoint, and routes with one router call."""
    desk = Desk()
    support = InMemoryCheckpointer()
    runner = Runner(support_graph(desk), support)
    with pytest.raises(PausedAtNode) as paused:
        runner.run("t1", {"input": "The CLI crashes on ctrl-c"})
    assert (paused.value.node, paused.value.step, paused.value.reason) == ("human_gate", 3, "awaiting approval")
    assert (desk.tickets, desk.sent) == (["BUG-1"], [])

    final = runner.resume("t1", {"approved": True})
    ticket = {"input": "The CLI crashes on ctrl-c", "route": "bug", "ticket": "BUG-1"}
    assert final == {**ticket, "approved": True, "output": "sent BUG-1"}, "resume goes on with the checkpointed state"
    assert steps(runner.history("t1")) == [
        (0, START), (1, "classify"), (2, "bug"), (3, "human_gate"), (4, HUMAN), (5, "send"),
    ], "resume picks up at the node after the latest checkpoint"
    assert [c.state for c in runner.history("t1")] == [
        {"input": "The CLI crashes on ctrl-c"},
        {"input": "The CLI crashes on ctrl-c", "route": "bug"},
        ticket,
        ticket,
        {**ticket, "approved": True},
        final,
    ], "history gives the whole state as of every step"
    assert runner.load_state("t1") == Checkpoint(5, "send", final)

    with pytest.raises(PausedAtNode):
        runner.run("t2", {"input": "I want my money back"})
    with pytest.raises(PausedAtNode) as paused:
        runner.resume("t2")
    assert (paused.value.node, paused.value.step) == ("human_gate", 4), "without a decision the gate pauses again"
    desk.relay_down = 1
    with pytest.raises(ConnectionError):
        runner.resume("t2", {"approved": True})
    assert runner.resume("t2")["output"] == "sent REF-2", "a human edit stays in force after a crash"

    desk.relay_down = 1
    with pytest.raises(ConnectionError):
        runner.run("t3", {"input": "A quote for 40 seats, please"})
    assert steps(runner.history("t3")) == [(0, START), (1, "classify"), (2, "sales")], "a node that raises leaves no checkpoint"
    assert runner.resume("t3")["output"] == "sent SAL-3"
    assert desk.tickets == ["BUG-1", "REF-2", "SAL-3"], "a resumed run does not repeat a finished step"
    assert desk.sent == ["BUG-1", "REF-2", "SAL-3"]

    llm = ScriptedRouter(["bug", "refund", "sales"])
    out = Runner(support_graph(desk, router=llm), InMemoryCheckpointer()).run(
        "t4", {"input": "Everything is broken", "approved": True}
    )
    assert (llm.calls, out["ticket"]) == (1, "BUG-4"), "the router runs once per step"
    for router in (ScriptedRouter(["spam"]), lambda state: None):
        with pytest.raises(GraphError):
            Runner(support_graph(desk, router=router), InMemoryCheckpointer()).run("t5", {"input": "hello?"})
    dead_end = StateGraph()
    dead_end.add_node("note", lambda state, ctx: {"noted": True})
    dead_end.set_entry("note")
    with pytest.raises(GraphError):
        Runner(dead_end, InMemoryCheckpointer()).run("t6", {})

    turns = 800
    docs = {f"doc-{i}": {"title": f"Doc {i}", "chunks": [i, i + 1, i + 2]} for i in range(1500)}
    chat = StateGraph(reducers={"messages": append})
    chat.add_node("chat", lambda state, ctx: {"messages": [f"turn {state['turn']}"], "turn": state["turn"] + 1})
    chat.set_entry("chat")
    chat.add_conditional_edges("chat", lambda state: "more" if state["turn"] < turns else "done", {"more": "chat", "done": END})
    checkpointer = InMemoryCheckpointer()
    runner = Runner(chat, checkpointer)
    start = time.perf_counter()
    final = runner.run("long", {"docs": docs, "messages": [], "turn": 0})
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, "checkpoints of a long session must stay cheap"
    assert final == {"docs": docs, "messages": [f"turn {i}" for i in range(turns)], "turn": turns}
    assert runner.load_state("long") == Checkpoint(turns, "chat", final), "a checkpoint restores the whole state"
    assert checkpointer.records("long")[-1] == Record(turns, "chat", {"messages": [f"turn {turns - 1}"], "turn": turns}), (
        "a checkpoint holds what its step wrote"
    )
    assert support.records("t1")[3] == Record(3, "human_gate", {}), "a checkpoint holds what its step wrote, without the pause marker"
    assert runner.history("long")[-1] == Checkpoint(turns, "chat", final), "history gives the whole state as of every step"

    book = StateGraph()
    book.add_node("write", Notebook())
    book.set_entry("write")
    book.add_conditional_edges("write", lambda state: "more" if len(state["pages"]) < 3 else "done", {"more": "write", "done": END})
    runner = Runner(book, InMemoryCheckpointer())
    runner.run("nb", {"title": "notes"})
    assert [c.state.get("pages") for c in runner.history("nb")] == [None, [1], [1, 2], [1, 2, 3]], (
        "a checkpoint keeps each value as it was when its step ran"
    )
    runner.load_state("nb").state["pages"].append(99)
    assert runner.load_state("nb").state["pages"] == [1, 2, 3], "changing a loaded state leaves the checkpoints alone"


def exact(value):
    """A comparable form that tells tuple from list, set from frozenset, bytes from str, True from 1 and 1.0, -0.0 from 0.0."""
    if isinstance(value, Record):
        return ("Record", value.step, value.node, exact(value.writes), exact(value.calls))
    if isinstance(value, dict):
        return ("dict", sorted((repr(exact(key)), exact(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, [exact(item) for item in value])
    if isinstance(value, (set, frozenset)):
        return (type(value).__name__, sorted(repr(exact(item)) for item in value))
    if isinstance(value, float):
        return ("float", value.hex())
    return (type(value).__name__, value)


TRICKY = {
    "order_id": 2**64 + 1,
    "vip": True,
    "score": -0.0,
    "pair": (3, "b"),
    "tags": {"vip", ("tier", 2), 7},
    "seen": frozenset({"faq", "pricing"}),
    "attachment": b"\x00\xff\x9cPK",
    "by_id": {7: "seven", "7": "the string seven", (2, 3): "a cell", None: "no id", True: "yes"},
    "lookalikes": [{"__tuple__": [1, 2]}, {"tuple": [1]}, {"type": "bytes", "data": "AAE="}, {"$set": []}, {"t": "tuple", "v": [1]}],
    "numbers": [True, 1, 1.0, -0.0, 0.1 + 0.2, 2**80, -(2**70), float("inf"), None],
    "text": "Zürich 東京 🚚 \u2028 next line",
    "nested": [("a", [b"x", {"k": (None, frozenset({1}))}]), [], ()],
    "empty": [{}, (), set(), frozenset(), b"", ""],
}


def import_graph() -> StateGraph:
    """load writes every tricky value; retry clears the error, a write of None; gate writes nothing and pauses."""
    graph = StateGraph(reducers={"log": append})
    graph.add_node("load", lambda state, ctx: {**TRICKY, "log": ["loaded"], "error": "timeout"})
    graph.add_node("retry", lambda state, ctx: {"error": None, "log": ["retried"]})
    graph.add_node("gate", lambda state, ctx: {} if state.get("approved") else {PAUSE: "check the import"})
    graph.add_node("done", lambda state, ctx: {"log": ["done"]})
    graph.set_entry("load")
    graph.add_edge("load", "retry")
    graph.add_edge("retry", "gate")
    graph.add_conditional_edges("gate", lambda state: "go" if state.get("approved") else "wait", {"go": "done", "wait": "gate"})
    graph.add_edge("done", END)
    return graph


@pytest.mark.skip("Part 2")
def test_sqlite_checkpoints(tmp_path) -> None:
    """Checkpoints survive a reopen of the SQLite file, every value exactly as its step wrote it."""
    for name, value in TRICKY.items():
        text = dumps(value)
        assert isinstance(text, str) and json.loads(text) is not None, "dumps writes JSON text"
        assert exact(loads(text)) == exact(value), f"dumps and loads keep {name} exactly"
    for name, value in TRICKY.items():
        shaped = json.loads(dumps(value))  # plain data that looks like an encoded value
        assert exact(loads(dumps(shaped))) == exact(shaped), f"a dict shaped like the encoding of {name} reads back as a dict"
    with pytest.raises(TypeError):
        dumps({"when": datetime.datetime(2026, 11, 1, 9, 30)})

    path = str(tmp_path / "checkpoints.sqlite3")
    store, twin = SQLiteCheckpointer(path), InMemoryCheckpointer()
    for checkpointer in (store, twin):
        with pytest.raises(PausedAtNode):
            Runner(import_graph(), checkpointer).run("a1", {"customer": "Ana", "log": []})
    store.close()

    store = SQLiteCheckpointer(path)  # another process opens the same file
    assert exact(store.records("a1")) == exact(twin.records("a1")), "a reopened file gives back every record exactly"
    assert store.records("a1")[3] == Record(3, "gate", {}), "a step that wrote nothing is still a checkpoint"
    final = Runner(import_graph(), store).resume("a1", {"approved": True})
    assert exact(final) == exact(Runner(import_graph(), twin).resume("a1", {"approved": True})), (
        "a session goes on from a reopened file"
    )
    assert (final["error"], final["log"]) == (None, ["loaded", "retried", "done"]), "a write of None is a write"

    with pytest.raises(TypeError):
        store.put("a2", Record(0, START, {"ok": 1, "when": datetime.datetime(2026, 11, 1, 9, 30)}))
    assert store.records("a2") == [], "a put that fails leaves no trace of its step"
    store.put("a2", Record(0, START, {"ok": 1}))
    with pytest.raises(ValueError):
        store.put("a2", Record(0, START, {"ok": 2}))
    with pytest.raises(ValueError):
        store.put("a1", Record(4, HUMAN, {"approved": False}))
    assert store.records("a2") == [Record(0, START, {"ok": 1})], "a step is written once"
    assert [(r.step, r.node) for r in store.records("a1")] == [(0, START), (1, "load"), (2, "retry"), (3, "gate"), (4, HUMAN), (5, "done")]
    calls = (
        ("call", ("billing", "quote", 7), {"id": "Q-7", "lines": [("refund", 50)]}),
        ("random", (), 0.25),
        ("now", (), 1_700_000_000.5),
    )
    store.put("a3", Record(0, START, {}, calls))
    store.close()
    store = SQLiteCheckpointer(path)
    assert exact(store.records("a3")) == exact([Record(0, START, {}, calls)]), "a step's recorded calls are kept too"
    store.close()


class Api:
    """A stand-in for an external API: counts its calls, and fails the next `failures` of them."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls = 0
        self.failures = 0

    def __call__(self, *args):
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise ConnectionError("billing API timed out")
        return self.handler(*args)


class Clock:
    """A clock that moves on a quarter of a second at every read."""

    def __init__(self, start: float) -> None:
        self.time = start
        self.reads = 0

    def __call__(self) -> float:
        self.reads += 1
        self.time += 0.25
        return self.time


def billing(op: str, *args):
    if op == "quote":
        (order,) = args
        return {"id": f"Q-{order}", "amount": 50, "lines": [("refund", 50)]}
    if op == "refund":
        quote_id, amount, note = args
        return {"refund": f"RF-{quote_id}", "amount": amount, "note": note}
    if op == "notify":
        return {"notified": args[0]}
    raise KeyError(op)


def quote(state, ctx):
    found = ctx.call("billing", "quote", state["order"])
    found["amount"] -= state["discount"]  # the discount goes into the API's answer itself
    found["lines"].append(("discount", -state["discount"]))
    return {"quote": found, "quoted_at": ctx.now()}


def review(state, ctx):
    if state.get("approved") is None:
        return {PAUSE: "approve the refund?", "asked_at": state.get("asked_at") or ctx.now()}
    return {}


def pay(state, ctx):
    ref = f"R-{ctx.random():.6f}"
    receipt = ctx.call("billing", "refund", state["quote"]["id"], state["quote"]["amount"], state.get("note"))
    return {"receipt": receipt, "ref": ref, "paid_at": ctx.now()}


def refund_graph(**nodes) -> StateGraph:
    graph = StateGraph()
    for name, fn in {"quote": quote, "review": review, "pay": pay, **nodes}.items():
        graph.add_node(name, fn)
    graph.set_entry("quote")
    graph.add_edge("quote", "review")
    graph.add_conditional_edges(
        "review",
        lambda state: {None: "wait", True: "pay", False: "stop"}[state.get("approved")],
        {"wait": "review", "pay": "pay", "stop": END},
    )
    graph.add_edge("pay", END)
    return graph


def pay_clock_first(state, ctx):  # reads the clock before it draws
    paid_at = ctx.now()
    ref = f"R-{ctx.random():.6f}"
    receipt = ctx.call("billing", "refund", state["quote"]["id"], state["quote"]["amount"], state.get("note"))
    return {"receipt": receipt, "ref": ref, "paid_at": paid_at}


def pay_full_amount(state, ctx):  # refunds the amount before the discount
    ref = f"R-{ctx.random():.6f}"
    receipt = ctx.call("billing", "refund", state["quote"]["id"], 50, state.get("note"))
    return {"receipt": receipt, "ref": ref, "paid_at": ctx.now()}


def pay_and_notify(state, ctx):  # makes one call more than the recording
    update = pay(state, ctx)
    ctx.call("billing", "notify", update["receipt"]["refund"])
    return update


def quote_without_clock(state, ctx):  # makes one call fewer
    found = ctx.call("billing", "quote", state["order"])
    found["amount"] -= state["discount"]
    found["lines"].append(("discount", -state["discount"]))
    return {"quote": found, "quoted_at": 1_700_000_000.25}


def quote_double_discount(state, ctx):  # a code change: the same calls, another update
    found = ctx.call("billing", "quote", state["order"])
    found["amount"] -= 2 * state["discount"]
    found["lines"].append(("discount", -2 * state["discount"]))
    return {"quote": found, "quoted_at": ctx.now()}


def pay_wall_clock(state, ctx):  # stamps the wall clock behind its context's back
    update = pay(state, ctx)
    return {**update, "paid_at": time.time()}


def pay_unstamped(state, ctx):  # a code change: the same calls, one channel fewer
    update = pay(state, ctx)
    del update["paid_at"]
    return update


@pytest.mark.skip("Part 3")
def test_record_and_replay() -> None:
    """Random draws, clock reads and API calls are recorded with their step and answered from it on replay."""
    api, clock = Api(billing), Clock(1_700_000_000.0)
    world = World(seed=7, clock=clock, apis={"billing": api})
    draws = random.Random(7)
    first, second = draws.random(), draws.random()
    checkpointer = InMemoryCheckpointer()
    runner = Runner(refund_graph(), checkpointer, world=world)

    with pytest.raises(PausedAtNode):
        runner.run("r1", {"order": 7, "discount": 5})
    api.failures = 1
    with pytest.raises(ConnectionError):
        runner.resume("r1", {"approved": True, "note": "goodwill"})
    final = runner.resume("r1")
    assert final["receipt"] == {"refund": "RF-Q-7", "amount": 45, "note": "goodwill"}
    assert final["ref"] == f"R-{second:.6f}" != f"R-{first:.6f}", "a node that crashed draws again when it runs again"

    recorded = {r.node: r.calls for r in checkpointer.records("r1")}
    assert recorded["quote"] == (
        ("call", ("billing", "quote", 7), {"id": "Q-7", "amount": 50, "lines": [("refund", 50)]}),
        ("now", (), 1_700_000_000.25),
    ), "a step records its calls in order, each with what it returned"
    assert recorded["review"] == (("now", (), 1_700_000_000.5),)
    assert recorded["pay"] == (
        ("random", (), second),
        ("call", ("billing", "refund", "Q-7", 45, "goodwill"), {"refund": "RF-Q-7", "amount": 45, "note": "goodwill"}),
        ("now", (), 1_700_000_000.75),
    ), "only the attempt that finished is recorded"
    assert recorded[START] == recorded[HUMAN] == ()

    seen = (api.calls, clock.reads, world.rng.getstate())
    for _ in range(2):
        assert runner.replay("r1") == final, "a replay comes to the same final state"
    assert (api.calls, clock.reads, world.rng.getstate()) == seen, "a replay calls nothing real"
    assert [r.step for r in checkpointer.records("r1")] == [0, 1, 2, 3, 4], "a replay writes no checkpoints"
    assert checkpointer.records("r1")[1].calls[0][2] == {"id": "Q-7", "amount": 50, "lines": [("refund", 50)]}, (
        "a replay leaves the recording as it was"
    )

    for nodes, step in [
        ({"pay": pay_clock_first}, 4),
        ({"pay": pay_full_amount}, 4),
        ({"pay": pay_and_notify}, 4),
        ({"quote": quote_without_clock}, 1),
        ({"quote": quote_double_discount}, 1),
        ({"pay": pay_wall_clock}, 4),
        ({"pay": pay_unstamped}, 4),
    ]:
        with pytest.raises(ReplayMismatch, match=f"step {step}"):
            Runner(refund_graph(**nodes), checkpointer, world=world).replay("r1")
    assert (api.calls, clock.reads, world.rng.getstate()) == seen, "a replay that goes wrong calls nothing real either"


def parse_sse(frame: str) -> dict:
    """One server-sent event: its fields (one space after the colon is dropped), with data parsed as JSON."""
    assert frame.endswith("\n\n") and "\n\n" not in frame[:-2], "each item is one event, closed by a blank line"
    event: dict = {}
    for line in frame[:-2].split("\n"):
        field, sep, value = line.partition(":")
        assert sep and field in ("id", "event", "data") and field not in event, f"unexpected line {line!r}"
        value = value[1:] if value.startswith(" ") else value
        event[field] = json.loads(value) if field == "data" else value
    return event


@pytest.mark.skip("Part 4")
def test_stream_updates() -> None:
    """Every checkpoint goes out as an SSE updates event once it is written; a pause ends the stream."""
    log: list[str] = []
    relay = {"down": 1}

    async def draft(state, ctx):
        await asyncio.sleep(0)
        log.append("draft")
        return {"messages": [f"draft for {state['to']}"], "draft": f"Hi {state['to']}"}

    def check(state, ctx):
        log.append("check")
        if not state.get("ok"):
            return {"messages": ["needs a look"], PAUSE: "send it?"}
        return {}

    async def send(state, ctx):
        await asyncio.sleep(0)
        log.append("send")
        if relay["down"]:
            relay["down"] -= 1
            raise ConnectionError("mail relay unavailable")
        return {"sent": state["draft"]}

    graph = StateGraph(reducers={"messages": append})
    graph.add_node("draft", draft)
    graph.add_node("check", check)
    graph.add_node("send", send)
    graph.set_entry("draft")
    graph.add_edge("draft", "check")
    graph.add_conditional_edges("check", lambda state: "go" if state.get("ok") else "wait", {"go": "send", "wait": "check"})
    graph.add_edge("send", END)
    runner = Runner(graph, InMemoryCheckpointer())

    async def watch(stream, events: list) -> None:
        async for frame in stream:
            event = parse_sse(frame)
            log.append(f"event {event.get('id', event['event'])}")
            written = [r.step for r in runner.checkpointer.records("u1")]
            assert "id" not in event or int(event["id"]) in written, "an event goes out only once its step is checkpointed"
            events.append(event)

    events: list = []
    asyncio.run(watch(stream_updates(runner, "u1", {"to": "Ana", "messages": ["hi"]}), events))
    assert events == [
        {"id": "0", "event": "updates", "data": {"node": START, "update": {"to": "Ana", "messages": ["hi"]}}},
        {"id": "1", "event": "updates", "data": {"node": "draft", "update": {"messages": ["draft for Ana"], "draft": "Hi Ana"}}},
        {"id": "2", "event": "updates", "data": {"node": "check", "update": {"messages": ["needs a look"]}}},
        {"event": "interrupt", "data": {"node": "check", "step": 2, "reason": "send it?"}},
    ], "an updates event carries what its step wrote; a pause sends interrupt and ends the stream"
    assert log == ["event 0", "draft", "event 1", "check", "event 2", "event interrupt"], (
        "each event goes out as soon as its step is checkpointed"
    )

    events = []
    with pytest.raises(ConnectionError):
        asyncio.run(watch(stream_updates(runner, "u1", patch={"ok": True}), events))
    assert events == [{"id": "3", "event": "updates", "data": {"node": HUMAN, "update": {"ok": True}}}], (
        "a resumed stream goes on with the session's next step"
    )
    events = []
    asyncio.run(watch(stream_updates(runner, "u1"), events))
    assert events == [
        {"id": "4", "event": "updates", "data": {"node": "send", "update": {"sent": "Hi Ana"}}},
        {"event": "end", "data": {"step": 4}},
    ], "reaching END sends end"
    assert runner.load_state("u1").state == {
        "to": "Ana", "messages": ["hi", "draft for Ana", "needs a look"], "draft": "Hi Ana", "ok": True, "sent": "Hi Ana",
    }

    async def first_two() -> list:
        stream = stream_updates(runner, "u2", {"to": "Bo", "messages": []})
        got = [parse_sse(await stream.__anext__()) for _ in range(2)]
        await stream.aclose()
        return got

    assert [event["id"] for event in asyncio.run(first_two())] == ["0", "1"]
    assert runner.load_state("u2").step == 1, "an event goes out only once its step is checkpointed"


@pytest.mark.skip("Part 5")
def test_nested_subgraphs() -> None:
    """A subgraph node checkpoints under its own namespace; resume goes back in where it stopped."""
    outbox: list[tuple[str, str]] = []
    down = {"account manager": 1}

    def say(text: str):
        return lambda state, ctx: {"messages": [text]}

    def mail(to: str, text: str):
        def send(state, ctx):
            if down.get(to):
                down[to] -= 1
                raise ConnectionError(f"cannot reach the {to}")
            outbox.append((to, state["draft"]))
            return {"messages": [text]}

        return send

    legal = StateGraph(reducers={"messages": append})
    legal.add_node("check", say("legal: checked"))
    legal.add_node("sign", lambda state, ctx: {} if state.get("signed") else {PAUSE: "needs a signature"})
    legal.set_entry("check")
    legal.add_edge("check", "sign")
    legal.add_conditional_edges("sign", lambda state: "done" if state.get("signed") else "wait", {"done": END, "wait": "sign"})

    review = StateGraph(reducers={"messages": append})
    review.add_node("draft", lambda state, ctx: {"messages": ["review: drafted"], "draft": f"Offer for {state['customer']}"})
    review.add_node("legal", legal)
    review.add_node("send", mail("account manager", "review: sent"))
    review.set_entry("draft")
    review.add_edge("draft", "legal")
    review.add_edge("legal", "send")
    review.add_edge("send", END)

    root = StateGraph(reducers={"messages": append})
    root.add_node("intake", say("intake"))
    root.add_node("review", review)
    root.add_node("send", mail("customer", "root: sent"))
    root.set_entry("intake")
    root.add_edge("intake", "review")
    root.add_edge("review", "send")
    root.add_edge("send", END)

    checkpointer = InMemoryCheckpointer()
    runner = Runner(root, checkpointer)
    with pytest.raises(PausedAtNode) as paused:
        runner.run("s1", {"customer": "Ana", "messages": []})
    assert (paused.value.namespace, paused.value.node, paused.value.step) == ("s1|review:2|legal:2", "sign", 2), (
        "a pause names the namespace it happened in"
    )
    assert [r.node for r in checkpointer.records("s1")] == [START, "intake"], "a subgraph node is checkpointed once it finishes"
    assert [r.node for r in checkpointer.records("s1|review:2")] == [START, "draft"]
    assert checkpointer.records("s1|review:2|legal:2")[0] == Record(
        0, START, {"customer": "Ana", "messages": ["intake", "review: drafted"], "draft": "Offer for Ana"}
    ), "a subgraph starts from its parent's state"

    with pytest.raises(ConnectionError):
        runner.resume("s1", {"signed": True})
    assert checkpointer.records("s1|review:2|legal:2")[-1] == Record(3, HUMAN, {"signed": True}), (
        "the edit goes to the subgraph that paused"
    )
    final = runner.resume("s1")
    assert outbox == [("account manager", "Offer for Ana"), ("customer", "Offer for Ana")], "each send runs once, in its own graph"
    assert [r.node for r in checkpointer.records("s1|review:2")] == [START, "draft", "legal", "send"], (
        "resume goes on inside the subgraph"
    )
    assert checkpointer.records("s1")[2] == Record(
        2, "review", {"messages": ["review: drafted", "legal: checked", "review: sent"], "draft": "Offer for Ana", "signed": True}
    ), "a subgraph hands its parent what its steps wrote"
    assert final == {
        "customer": "Ana",
        "messages": ["intake", "review: drafted", "legal: checked", "review: sent", "root: sent"],
        "draft": "Offer for Ana",
        "signed": True,
    }

    research = StateGraph(reducers={"notes": append})
    research.add_node("search", lambda state, ctx: {"notes": [f"finding {len(state['notes']) + 1}"]})
    research.set_entry("search")
    research.add_edge("search", END)
    loop = StateGraph(reducers={"notes": append})
    loop.add_node("research", research)
    loop.set_entry("research")
    loop.add_conditional_edges("research", lambda state: "more" if len(state["notes"]) < 3 else "done", {"more": "research", "done": END})
    checkpointer = InMemoryCheckpointer()
    assert Runner(loop, checkpointer).run("r1", {"notes": []}) == {"notes": ["finding 1", "finding 2", "finding 3"]}, (
        "every run of a subgraph node gets a namespace of its own"
    )
    assert checkpointer.records("r1|research:2") == [
        Record(0, START, {"notes": ["finding 1"]}),
        Record(1, "search", {"notes": ["finding 2"]}),
    ]
