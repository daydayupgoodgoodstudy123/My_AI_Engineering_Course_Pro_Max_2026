import asyncio
import csv
import dataclasses
import io
import math
import sqlite3
import time
from contextlib import closing

import pytest
from hybridmem.context import memory_block
from hybridmem.fusion import FusionConfig, Hit, Query, recall
from hybridmem.graph import Edge, GraphStore
from hybridmem.memory import KVKey, Mem0, Viewer
from hybridmem.pipeline import Candidate, Lookup, Message, WritePolicy, ingest
from hybridmem.sqlite_store import load, save
from hybridmem.temporal import paths, value_at


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def rids(hits) -> list[str]:
    return [record.rid for _, record in hits]


@pytest.mark.skip("Part 1")
def test_scoped_search() -> None:
    """Search shows a caller only their own memories that match the query, and the graph keeps one current edge per fact, fast."""
    clock = Clock(1_000.0)
    mem = Mem0(clock=clock)
    mem.add("ava is planning the acme offsite in lisbon", user_id="ava", session_id="s1", importance=0.6, kv_triples=(("project", "offsite"),))
    mem.add("the login code for this chat is 4471", user_id="ava", session_id="s1", scope="session", kv_triples=(("login_code", "chat"),))
    mem.add("bob says the acme acquisition plan is confidential", user_id="bob", session_id="s7", scope="session", importance=0.9)
    mem.add("bob named the acme plan bluebird", user_id="bob", session_id="s7", scope="agent", importance=0.9)
    mem.add("ava wants the acme plan in one line", user_id="ava", session_id="s1", scope="agent", agent_id="writer")

    ava = Viewer("ava", "s2")
    assert memory_block(mem, "acme plan", ava) == "- [m001] ava is planning the acme offsite in lisbon", (
        "a caller sees their own memories and nobody else's"
    )
    assert mem.search("refund invoice", viewer=ava) == [], "a query that matches no memory finds nothing"
    assert rids(mem.search("acme plan", viewer=Viewer("bob", "s7"))) == ["m004", "m003"], (
        "bob sees his own session and agent memories"
    )
    assert rids(mem.search("login code", viewer=Viewer("ava", "s1"))) == ["m002"], "a session memory is there in its session"
    assert mem.search("login code", viewer=ava) == [], "a session memory stays in its session"
    assert rids(mem.search("acme plan", viewer=Viewer("ava", "s2", "writer"))) == ["m005", "m001"], (
        "an agent memory stays with its agent"
    )

    for i in range(30):
        mem.add(f"refund for invoice {4700 + i} was approved", user_id=f"u{i:02d}", session_id="x", scope="session")
    mine = mem.add("ava asked if her refund was approved", user_id="ava", session_id="s2", scope="session")
    assert rids(mem.search("refund approved", viewer=ava, top_k=2)) == [mine], (
        "a caller's own memories are found however many others match better"
    )

    def lived() -> list[tuple]:
        return [(e.obj, e.valid_from, e.valid_to) for e in mem.graph.history("ava", "lives_in")]

    clock.now = 2_000.0
    mem.add("ava lives in berlin", user_id="ava", session_id="s1", graph_triples=(("ava", "lives_in", "berlin"),))
    mem.add("ava works at acme", user_id="ava", session_id="s1", graph_triples=(("ava", "works_at", "acme"),))
    assert [(e.relation, e.obj) for e in mem.graph.neighbors("ava")] == [("lives_in", "berlin"), ("works_at", "acme")], (
        "each relation has its own current edge"
    )
    clock.now = 3_000.0
    moved = mem.add("ava moved to lisbon", user_id="ava", session_id="s2", graph_triples=(("ava", "lives_in", "lisbon"),))
    assert lived() == [("berlin", 2_000.0, 3_000.0), ("lisbon", 3_000.0, None)], "a contradicted edge is closed, not deleted"
    clock.now = 4_000.0
    mem.add("ava is still in lisbon", user_id="ava", session_id="s3", graph_triples=(("ava", "lives_in", "lisbon"),))
    assert lived() == [("berlin", 2_000.0, 3_000.0), ("lisbon", 3_000.0, None)], "restating the current fact changes nothing"
    assert mem.graph.current("ava", "lives_in").rid == moved, "the current edge is still the one that first said it"
    restated = mem.graph.add_edge("ava", "lives_in", "lisbon", rid="m999", at=4_500.0, weight=0.25)
    assert restated is mem.graph.current("ava", "lives_in"), "restating returns the edge that already holds"
    assert restated.weight == 1.0, "restating the current fact changes nothing"
    clock.now = 5_000.0
    mem.add("ava moved back to berlin", user_id="ava", session_id="s3", graph_triples=(("ava", "lives_in", "berlin"),))
    assert lived() == [("berlin", 2_000.0, 3_000.0), ("lisbon", 3_000.0, 5_000.0), ("berlin", 5_000.0, None)], (
        "an old fact can come back"
    )

    graph = GraphStore()
    for i in range(24_000):  # last night's snapshot of the billing graph
        graph.restore(Edge(f"c{i}", "billed_to", f"e{i % 50}", "m900", float(i)))
    movers = [(f"c{i}", f"e{(i + 1) % 50}") for i in range(0, 24_000, 6)]
    start = time.perf_counter()
    for k, (name, entity) in enumerate(movers):
        graph.add_edge(name, "billed_to", entity, rid="m901", at=24_000.0 + k)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05, "writes must not slow down as the graph grows"
    assert len(graph.all_edges()) == 28_000, "a contradicted edge is closed, not deleted"
    assert sum(e.valid for e in graph.all_edges()) == 24_000, "every write closes the edge it contradicts, restored ones too"
    assert [(e.obj, e.valid_to) for e in graph.history("c4242", "billed_to")] == [("e42", 24_707.0), ("e43", None)], (
        "a write closes the edge it contradicts at the moment of the write"
    )
    assert graph.current("c4243", "billed_to").obj == "e43", "a customer who did not move keeps their edge"


def exact(value):
    """A comparable form that tells 1 from 1.0, a tuple from a list, and floats bit for bit."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, {f.name: exact(getattr(value, f.name)) for f in dataclasses.fields(value)})
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, [exact(item) for item in value])
    if isinstance(value, float):
        return ("float", value.hex())
    return (type(value).__name__, value)


def dump(mem: Mem0) -> dict:
    return {
        "records": [exact(record) for record in mem.vector.records()],
        "kv": sorted((key.user_id, key.fact_type, key.entity, record.rid) for key, record in mem.kv.items()),
        "edges": [exact(edge) for edge in mem.graph.all_edges()],
    }


@pytest.mark.skip("Part 2")
def test_sqlite_roundtrip(tmp_path) -> None:
    """The three stores survive a save and a load exactly, and a loaded memory carries on where it left off."""
    path = str(tmp_path / "memory.sqlite3")
    clock = Clock(1_700_000_000.0)
    mem = Mem0(clock=clock)
    mem.add(
        "Ava zieht nach Lissabon 🏠",
        user_id="ava",
        session_id="s1",
        importance=0.1 + 0.2,
        tags=("travel", "profile"),
        kv_triples=(("city", "home"),),
        graph_triples=(("ava", "lives_in", "lisbon"),),
    )
    clock.now = 1_700_000_000.0 + 2**-22  # finer than a microsecond
    mem.add(
        "ava works at acme",
        user_id="ava",
        session_id="s1",
        scope="session",
        kv_triples=(("employer", "ava"),),
        graph_triples=(("ava", "works_at", "acme"),),
    )
    clock.now = 1_699_999_876.544  # written by a node whose clock runs behind
    mem.add(
        "refund for invoice 4711, approved",
        user_id="bob",
        session_id="s9",
        scope="agent",
        agent_id="billing",
        importance=0.9,
        tags=("billing", "refund, approved"),
        kv_triples=(("refund", "4711"),),
    )
    clock.now = 1_700_000_200.0
    mem.add(
        "ava moved to porto",
        user_id="ava",
        session_id="s2",
        importance=0.7,
        kv_triples=(("city", "home"),),
        graph_triples=(("ava", "lives_in", "porto"),),
    )
    mem.graph.add_edge("acme", "based_in", "porto", rid="m002", at=1_600_000_000.0, weight=0.95)  # backdated
    mem.record("m001").last_read = 1_700_000_250.5

    save(mem, path)
    back = load(path, clock=clock)
    assert dump(back) == dump(mem), "every store reads back exactly"
    assert back.kv.get(KVKey("ava", "city", "home")) is back.record("m004"), "a KV entry points at the stored record, not a copy"

    clock.now = 1_700_000_300.0
    assert back.add(
        "ava moved back to lisbon", user_id="ava", session_id="s3", graph_triples=(("ava", "lives_in", "lisbon"),)
    ) == "m005", "a loaded memory keeps counting rids"
    assert back.record("m005").ts == 1_700_000_300.0, "a loaded memory runs on the clock it was given"
    assert [(e.obj, e.valid) for e in back.graph.history("ava", "lives_in")] == [
        ("lisbon", False),
        ("porto", False),
        ("lisbon", True),
    ], "a loaded graph still knows which edge holds now"
    back.record("m002").last_read = 1_700_000_301.0
    save(back, path)
    again = load(path, clock=clock)
    assert dump(again) == dump(back), "a second save replaces what the first one wrote"

    for i in range(1_000):
        again.add(f"note {i}", user_id="ava", session_id="s3")
    save(again, path)
    big = load(path, clock=clock)
    assert dump(big) == dump(again), "a memory past m999 reads back in order"
    assert big.add("one more note", user_id="ava", session_id="s3") == "m1006", "rids keep counting past m999"

    with closing(sqlite3.connect(path)) as db:
        assert db.execute(
            "SELECT fact_type, entity, rid FROM kv WHERE user_id = ? ORDER BY fact_type", ("ava",)
        ).fetchall() == [("city", "home", "m004"), ("employer", "ava", "m002")], "the export job reads one kv row per key"
        assert db.execute("SELECT rid, text FROM records WHERE user_id = ?", ("bob",)).fetchall() == [
            ("m003", "refund for invoice 4711, approved")
        ], "the export job reads records by user"
        assert db.execute(
            "SELECT obj, valid_to IS NULL FROM edges WHERE subject = ? AND relation = ? ORDER BY valid_from",
            ("ava", "lives_in"),
        ).fetchall() == [("lisbon", 0), ("porto", 0), ("lisbon", 1)], "the export job sees closed edges too"


@pytest.mark.skip("Part 3")
def test_fused_recall() -> None:
    """Recall fuses what the three stores find into one weighted score, and reading a memory makes it recent."""
    clock = Clock(0.0)
    mem = Mem0(clock=clock)
    flat = mem.add("ava rents a flat in lisbon, flat 2b", user_id="ava", session_id="s1", importance=0.5)
    mem.add("bob rents a flat in lisbon too", user_id="bob", session_id="s9", importance=0.9, kv_triples=(("landlord", "flat"),))
    clock.now = 500.0
    home = mem.add("ava's address is rua augusta 10", user_id="ava", session_id="s1", importance=0.75, kv_triples=(("address", "home"),))
    clock.now = 1_000.0
    lease = mem.add("ava signed the lisbon lease with acme", user_id="ava", session_id="s1", importance=0.25, kv_triples=(("landlord", "flat"),))
    mem.graph.add_edge("ava", "customer_of", "acme", rid=lease, at=1_000.0, weight=0.75)
    mem.graph.add_edge("acme", "based_in", "porto", rid=lease, at=1_000.0, weight=0.5)
    mem.add("bob is on the acme deal", user_id="bob", session_id="s9", importance=0.9, graph_triples=(("bob", "works_on", "acme"),))
    carol = mem.add("carol manages ava's account", user_id="ava", session_id="s1", importance=0.5)
    mem.graph.add_edge("carol", "works_at", "acme", rid=carol, at=1_000.0, weight=0.875)
    mem.graph.add_edge("acme", "account_manager", "carol", rid=carol, at=1_000.0, weight=0.5)
    clock.now = 1_500.0
    viewing = mem.add("flat viewing at 5pm in lisbon", user_id="ava", session_id="s2", scope="session", importance=1.0)
    mem.add("the wifi code for the flat is 1234", user_id="ava", session_id="s1", scope="session", kv_triples=(("wifi", "flat"),))
    mem.add("ava likes a flat white at 8", user_id="ava", session_id="s1", scope="agent")
    mem.add("ava's dentist appointment is on friday", user_id="ava", session_id="s1")
    clock.now = 1_700.0
    mem.add("ava lived in berlin", user_id="ava", session_id="s1", graph_triples=(("ava", "lives_in", "berlin"),))
    clock.now = 1_800.0
    moved = mem.add("ava moved to lisbon", user_id="ava", session_id="s1", graph_triples=(("ava", "lives_in", "lisbon"),))
    clock.now = 2_500.0  # written by a node whose clock runs ahead
    keys = mem.add("keys for the lisbon flat collected", user_id="ava", session_id="s1", importance=0.5)
    mem.record(flat).last_read = 1_500.0

    clock.now = 2_000.0
    query = Query(
        "lisbon flat",
        kv_keys=(("address", "home"), ("landlord", "flat"), ("wifi", "flat")),
        entities=("acme", "berlin"),
    )
    config = FusionConfig(
        w_relevance=0.5, w_importance=0.25, w_recency=0.5, halflife_s=1_000.0, scope_weights={"user": 1.0, "session": 0.5}
    )
    ava = Viewer("ava", "s2")
    hits = recall(mem, query, viewer=ava, config=config, top_k=10)
    expected = [
        Hit(keys, 0.5 * (2 / math.sqrt(12)) + 0.25 * 0.5 + 0.5 * 1.0, 2 / math.sqrt(12)),
        Hit(home, 0.5 * 1.0 + 0.25 * 0.75 + 0.5 * 0.5**1.5, 1.0),
        Hit(flat, 0.5 * (3 / math.sqrt(20)) + 0.25 * 0.5 + 0.5 * 0.5**0.5, 3 / math.sqrt(20)),
        Hit(lease, 0.5 * 1.0 + 0.25 * 0.25 + 0.5 * 0.5, 1.0),
        Hit(carol, 0.5 * 0.875 + 0.25 * 0.5 + 0.5 * 0.5, 0.875),
        Hit(moved, 0.5 * (1 / math.sqrt(8)) + 0.25 * 0.5 + 0.5 * 0.5**0.2, 1 / math.sqrt(8)),
        Hit(viewing, 0.5 * (0.5 * (2 / math.sqrt(12)) + 0.25 * 1.0 + 0.5 * 0.5**0.5), 2 / math.sqrt(12)),
    ]
    assert [h.rid for h in hits] == [h.rid for h in expected], "the memories some store finds, best first, ties to the lower rid"
    assert [h.relevance for h in hits] == pytest.approx([h.relevance for h in expected], rel=1e-12), (
        "relevance is the best a store gives: cosine of token counts, a KV hit, or an edge weight"
    )
    assert [h.score for h in hits] == pytest.approx([h.score for h in expected], rel=1e-12), (
        "score is the scope-weighted sum of relevance, importance and recency"
    )

    def last_reads() -> dict:
        return {r.rid: r.last_read for r in mem.vector.records() if r.last_read is not None}

    assert last_reads() == {h.rid: 2_000.0 for h in expected}, "the records returned are read now"
    assert mem.record(keys).ts == 2_500.0, "reading a record does not rewrite it"

    clock.now = 2_500.0
    hits = recall(mem, query, viewer=ava, config=config, top_k=4)
    assert [(h.rid, h.score) for h in hits] == [
        (home, pytest.approx(0.5 + 0.25 * 0.75 + 0.5 * 0.5**0.5, rel=1e-12)),
        (lease, pytest.approx(0.5 + 0.25 * 0.25 + 0.5 * 0.5**0.5, rel=1e-12)),
        (carol, pytest.approx(0.5 * 0.875 + 0.25 * 0.5 + 0.5 * 0.5**0.5, rel=1e-12)),
        (keys, pytest.approx(0.5 * (2 / math.sqrt(12)) + 0.25 * 0.5 + 0.5 * 1.0, rel=1e-12)),
    ], "a memory read at the last recall counts as recent"
    assert last_reads() == {
        **{h.rid: 2_000.0 for h in expected},
        **{h.rid: 2_500.0 for h in hits},
    }, "only the records returned are read"

    twins = Mem0(clock=Clock(100.0))
    first = twins.add("call the landlord", user_id="ava", session_id="s1", kv_triples=(("todo", "landlord"),))
    second = twins.add("call the landlord", user_id="ava", session_id="s1", kv_triples=(("todo", "plumber"),))
    twins.add("buy milk", user_id="ava", session_id="s1")
    twins.clock = Clock(5_000.0)
    flat_out = FusionConfig(w_relevance=1.0, w_importance=1.0, w_recency=1.0, halflife_s=0.0)
    hits = recall(twins, Query("", kv_keys=(("todo", "plumber"), ("todo", "landlord"))), viewer=Viewer("ava", "s4"), config=flat_out)
    assert [(h.rid, h.score) for h in hits] == [(first, 2.5), (second, 2.5)], (
        "a key lookup needs no text; halflife 0 turns recency off; weights are used as given; ties go to the lower rid"
    )


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def stream(events):
    for event in events:
        yield event


PROPOSALS = {
    "moving to lisbon next week, cannot wait for pastel de nata": [
        Candidate("ava", "lives_in", "Lisbon, Portugal", 0.95),
        Candidate("ava", "likes", 'pastel de "nata"', 0.45),
    ],
    "new job at acme as cto, office in porto, I surf and have a dog": [
        Candidate("ava", "works_at", "acme", 0.9),
        Candidate("ava", "height", "1,70 m", 0.3),
        Candidate("ava", "owns", "dog", 0.5),
        Candidate("ava", "role", "cto", 0.7),
        Candidate("acme", "based_in", "porto", 0.7),
        Candidate("ava", "likes", "surfing", 0.7),
    ],
    "bob loves lisbon too": [Candidate("bob", "likes", "lisbon", 0.8)],
    "still in lisbon, portugal": [
        Candidate("ava", "lives_in", "Lisbon, Portugal", 0.9),
        Candidate("ava", "country", "Portugal", 0.8),
        Candidate("ava", "city", "Lisbon", 0.7),
        Candidate("ava", "likes", "lisbon", 0.6),
    ],
    "we moved to porto after all": [Candidate("ava", "lives_in", "Rua Augusta 10\n4000 Porto", 0.8)],
}

EVENTS = [
    Message(1, "ava", "s1", "moving to lisbon next week, cannot wait for pastel de nata"),
    Message(2, "ava", "s1", "thanks!"),
    Message(3, "ava", "s1", "new job at acme as cto, office in porto, I surf and have a dog"),
    Message(4, "bob", "s9", "bob loves lisbon too"),
    Lookup(5, "bob", "s9", "lisbon"),
    Message(6, "ava", "s2", "still in lisbon, portugal"),
    Lookup(7, "ava", "s2", "lisbon"),
    Message(8, "ava", "s3", "we moved to porto after all"),
    Message(9, "ava", "s3", "ok, see you"),
    Lookup(10, "ava", "s3", "porto lisbon"),
    Lookup(11, "ava", "s3", "porto"),
    Lookup(12, "bob", "s9", "porto"),
    Lookup(13, "ava", "s3", "acme job"),
]


@pytest.mark.skip("Part 4")
def test_write_audit() -> None:
    """The write path gates graph writes, refreshes hot embeddings, and audits every decision as it happens."""
    extracted: list[str] = []

    async def extract(text: str) -> list[Candidate]:
        extracted.append(text)
        return PROPOSALS.get(text, [])

    reembedded: list[str] = []

    async def reembed(record) -> None:
        reembedded.append(record.rid)

    policy = WritePolicy(max_edges=3, min_confidence=0.5, reembed_every=3, reembed_top=3, top_k=2)
    mem = Mem0(clock=Clock(100.0))
    out = collect(ingest(stream(EVENTS), mem, extract=extract, reembed=reembed, policy=policy))
    rows = list(csv.reader(io.StringIO("".join(out))))
    assert len(rows) == len(out), "each yielded string is exactly one CSV row"
    assert rows == [
        ["1", "edge", "ava", "lives_in", "Lisbon, Portugal", "write", "new"],
        ["1", "edge", "ava", "likes", 'pastel de "nata"', "drop", "low_confidence"],
        ["3", "edge", "ava", "works_at", "acme", "write", "new"],
        ["3", "edge", "ava", "height", "1,70 m", "drop", "low_confidence"],
        ["3", "edge", "ava", "owns", "dog", "drop", "over_cap"],
        ["3", "edge", "ava", "role", "cto", "write", "new"],
        ["3", "edge", "acme", "based_in", "porto", "write", "new"],
        ["3", "edge", "ava", "likes", "surfing", "drop", "over_cap"],
        ["4", "edge", "bob", "likes", "lisbon", "write", "new"],
        ["6", "edge", "ava", "lives_in", "Lisbon, Portugal", "skip", "restated"],
        ["6", "edge", "ava", "country", "Portugal", "write", "new"],
        ["6", "edge", "ava", "city", "Lisbon", "write", "new"],
        ["6", "edge", "ava", "likes", "lisbon", "drop", "over_cap"],
        ["8", "edge", "ava", "lives_in", "Rua Augusta 10\n4000 Porto", "write", "conflict"],
        ["8", "edge", "ava", "lives_in", "Lisbon, Portugal", "invalidate", "superseded"],
        ["10", "record", "m005", "", "", "reembed", "uses=2"],
        ["10", "record", "m001", "", "", "reembed", "uses=1"],
        ["10", "record", "m004", "", "", "reembed", "uses=1"],
        ["13", "record", "m003", "", "", "reembed", "uses=2"],
        ["13", "record", "m006", "", "", "reembed", "uses=2"],
    ], "one audit row per decision, in order"
    assert reembedded == ["m005", "m001", "m004", "m003", "m006"], "re-embedding goes through the embedder"
    assert extracted == [e.text for e in EVENTS if isinstance(e, Message)], "the extractor runs once per message"
    edge = mem.graph.current("ava", "lives_in")
    assert (edge.obj, edge.rid, edge.weight) == ("Rua Augusta 10\n4000 Porto", "m006", 0.8), (
        "a written edge is asserted by its message's record, weighted by its confidence"
    )
    assert [mem.graph.current("ava", r) for r in ("likes", "owns", "height")] == [None, None, None], (
        "dropped candidates never reach the graph"
    )

    pulled: list[int] = []

    async def trickle():
        for event in EVENTS:
            pulled.append(event.seq)
            yield event

    async def first_row() -> str:
        agen = ingest(trickle(), Mem0(clock=Clock(100.0)), extract=extract, reembed=reembed, policy=policy)
        row = await agen.__anext__()
        await agen.aclose()
        return row

    assert next(csv.reader([asyncio.run(first_row())]))[:5] == ["1", "edge", "ava", "lives_in", "Lisbon, Portugal"], (
        "the first row is the first decision"
    )
    assert pulled == [1], "each row goes out as soon as it is decided"


JAN, FEB, MAR, APR, MAY, JUN = 0.0, 31.0, 59.0, 90.0, 120.0, 151.0


def describe(found) -> list[str]:
    return [
        f"{p.weight} {p.edges[0].subject} " + " ".join(f"-{e.relation}-> {e.obj}" for e in p.edges) for p in found
    ]


@pytest.mark.skip("Part 5")
def test_graph_as_of() -> None:
    """The graph answers for the past: what held at a moment, and every path that held then."""
    g = GraphStore()
    g.add_edge("ava", "lives_in", "berlin", rid="m001", at=JAN)
    g.add_edge("ava", "lives_in", "lisbon", rid="m002", at=MAY)
    assert value_at(g, "ava", "lives_in", MAR) == "berlin", "a closed edge still answers for its own time"
    assert value_at(g, "ava", "lives_in", MAY) == "lisbon", "an edge holds from valid_from up to, not including, valid_to"
    assert value_at(g, "ava", "lives_in", JAN - 1) is None, "nothing held before the first assertion"
    assert value_at(g, "ava", "lives_in", JUN) == "lisbon"

    for subject, relation, obj, at, weight in [
        ("ava", "manages", "bob", JAN, 1.0),
        ("bob", "reports_to", "ava", JAN, 1.0),
        ("ava", "customer_of", "globex", JAN, 1.0),
        ("globex", "managed_by", "carol", JAN, 0.75),
        ("bob", "works_with", "carol", FEB, 0.75),
        ("ava", "partner_of", "globex", JAN, 0.5),
        ("ava", "mentors", "carol", FEB, 0.5),
        ("bob", "knows", "dave", JAN, 0.5),
        ("dave", "refers", "carol", JAN, 1.0),
        ("dave", "knows", "erin", JAN, 0.5),
        ("erin", "knows", "carol", JAN, 1.0),
        ("globex", "managed_by", "dave", APR, 0.5),
        ("initech", "managed_by", "carol", FEB, 0.5),
        ("ava", "customer_of", "initech", MAY, 0.875),
        ("ava", "mentors", "erin", JUN, 1.0),
    ]:
        g.add_edge(subject, relation, obj, rid="m100", at=at, weight=weight)

    assert describe(paths(g, "ava", "carol", at=MAR)) == [
        "0.75 ava -customer_of-> globex -managed_by-> carol",
        "0.75 ava -manages-> bob -works_with-> carol",
        "0.5 ava -mentors-> carol",
        "0.5 ava -manages-> bob -knows-> dave -refers-> carol",
        "0.375 ava -partner_of-> globex -managed_by-> carol",
    ], "every path that held in March, best first: weight, then hops, then alphabetical"
    assert describe(paths(g, "ava", "carol", at=MAR, max_hops=2)) == [
        "0.75 ava -customer_of-> globex -managed_by-> carol",
        "0.75 ava -manages-> bob -works_with-> carol",
        "0.5 ava -mentors-> carol",
        "0.375 ava -partner_of-> globex -managed_by-> carol",
    ], "max_hops counts edges"
    assert describe(paths(g, "ava", "carol", at=APR)) == [
        "0.75 ava -manages-> bob -works_with-> carol",
        "0.5 ava -mentors-> carol",
        "0.5 ava -customer_of-> globex -managed_by-> dave -refers-> carol",
        "0.5 ava -manages-> bob -knows-> dave -refers-> carol",
        "0.25 ava -partner_of-> globex -managed_by-> dave -refers-> carol",
    ], "every hop has to hold at that moment"
    assert describe(paths(g, "ava", "carol", at=JUN)) == [
        "1.0 ava -mentors-> erin -knows-> carol",
        "0.75 ava -manages-> bob -works_with-> carol",
        "0.5 ava -manages-> bob -knows-> dave -refers-> carol",
        "0.4375 ava -customer_of-> initech -managed_by-> carol",
        "0.25 ava -partner_of-> globex -managed_by-> dave -refers-> carol",
    ], "in June the same question has other answers"
    assert paths(g, "carol", "ava", at=MAR) == [], "edges are followed from subject to object"
    assert paths(g, "ava", "carol", at=JAN - 1) == [], "no path held before any edge did"
