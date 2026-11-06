import asyncio
import json
import math
import random
import time

import pytest
from memgpt.archival import ArchivalRecord, ArchivalStore
from memgpt.archive_db import SqliteArchive
from memgpt.bm25 import BM25, recall_at_k
from memgpt.context import MainContext
from memgpt.core import CoreLimitError, TypedCore
from memgpt.pager import page_stream
from memgpt.tokens import tokenize
from memgpt.tools import MemoryTools, ToolCall, run_scripted_agent


def jaccard_top(records: list[ArchivalRecord], query: str, top_k: int) -> list:
    """Archival search as the lesson ships it, one full scan per query."""
    q = set(tokenize(query))
    scored = []
    for record in records:
        r = set(tokenize(record.text))
        overlap = len(q & r)
        if overlap:
            scored.append((overlap / (len(q) + len(r) - overlap), record))
    scored.sort(key=lambda item: -item[0])
    return scored[:top_k]


@pytest.mark.skip("Part 1")
def test_tools_and_budget() -> None:
    """Facts keep their citations, core edits are unambiguous, the context keeps to its token
    budget, and archival search stays fast without changing its answers."""
    ctx = MainContext(max_tokens=40)
    tools = MemoryTools(ctx, ArchivalStore(), session_id="s7")
    ctx.append("user", "my name is ava and I ship agents for a living")
    ctx.append("assistant", "noted. what are you building right now?")
    ctx.append("user", "a retrieval bot for our sales org, 12 tools so far")
    fact = "ava is building a retrieval bot with 12 tools for sales"
    observations = run_scripted_agent(
        tools, [ToolCall("archival_memory_insert", {"text": fact, "tags": ("project", "ava")})]
    )
    ctx.append("assistant", "12 tools is in the long-horizon band; plan for drift")
    observations += run_scripted_agent(
        tools,
        [
            ToolCall(
                "archival_memory_insert",
                {"text": "long-horizon tool chains drift after 20 steps per BFCL V4", "tags": ("bfcl",)},
            ),
            ToolCall("archival_memory_search", {"query": "retrieval bot tool chains drift", "top_k": 2}),
        ],
    )
    assert observations == [
        "stored a001 (1 records)",
        "stored a002 (2 records)",
        "a002 [s7#4] long-horizon tool chains drift after 20 steps per BFCL V4\n"
        "a001 [s7#3] ava is building a retrieval bot with 12 tools for sales",
    ], "a retrieved fact cites the session and the turn it was stored at"

    ctx.core["human"] = "name=ava, stack=java"
    observation = tools.core_memory_replace("human", "ava", "eva")
    assert (observation.startswith("error:"), ctx.core["human"]) == (True, "name=ava, stack=java"), (
        "a replace whose old text occurs more than once is refused and changes nothing"
    )
    assert tools.core_memory_replace("human", "name=ava", "name=eva") == "core[human] replaced"
    assert ctx.core["human"] == "name=eva, stack=java"
    assert tools.core_memory_replace("human", "name=ava", "name=x").startswith("error:")
    assert ctx.core["human"] == "name=eva, stack=java"

    small = MainContext(max_tokens=8, core={"persona": "terse"})
    for text in ("ship it", "run evals", "page out"):
        small.append("user", text)
    assert [m.text for m in small.messages] == ["run evals", "page out"], (
        "every message costs approx_tokens(text), and the messages kept fit max_tokens"
    )
    assert (small.tokens(), [m.turn for m in small.recall]) == (6, [1]), "core sections do not count toward max_tokens"
    small.append("user", "go")
    assert [m.text for m in small.messages] == ["run evals", "page out", "go"], (
        "a context that costs exactly max_tokens fits"
    )
    paged = small.append("assistant", "a reply long enough to fill the whole context on its own")
    assert ([m.turn for m in paged], [m.turn for m in small.messages]) == ([2, 3, 4], [5]), (
        "the newest message stays, even when it alone is over budget"
    )
    found = MemoryTools(small, ArchivalStore(), "s8").conversation_search("RUN EVALS")
    assert found == "t2 user: run evals", "paged-out messages stay searchable"

    rng = random.Random(7)
    vocab = [f"w{i}" for i in range(6000)]
    big = ArchivalStore()
    for i in range(20_000):
        words = [rng.choice(vocab) for _ in range(rng.randint(6, 12))]
        big.insert(" ".join(words), session_id=f"s{i % 50}", turn_id=i)
    queries = [" ".join(rng.choice(vocab) for _ in range(3)) for _ in range(150)]
    start = time.perf_counter()
    results = [big.search(query, top_k=5) for query in queries]
    assert time.perf_counter() - start < 0.08, "archival search should stay fast on a large archive"

    dupes = ArchivalStore()
    for text, session, turn in (
        ("deploy target is aws lambda", "s1", 9),
        ("Deploy target: AWS Lambda?", "s2", 5),
        ("deploy target is aws lambda", "s3", 2),
        ("drift drift tool chains", "s4", 1),
    ):
        dupes.insert(text, session_id=session, turn_id=turn)
    a001, a002, a003, a004 = dupes.records()
    assert dupes.search("Lambda? drift drift tool", top_k=5) == [(0.5, a004), (1 / 6, a002)], (
        "scores are what they were: the Jaccard overlap of distinct tokens, split as before"
    )
    assert dupes.search("deploy target", top_k=5) == [(0.4, a001), (0.4, a003), (0.2, a002)], (
        "the same fact from two sessions stays two records, each with its own citation, in insertion order"
    )
    records = big.records()
    for query, hits in list(zip(queries, results))[:8]:
        assert hits == jaccard_top(records, query, 5), "results are what they were, ties in insertion order"


@pytest.mark.skip("Part 2")
def test_archive_roundtrip(tmp_path) -> None:
    """Archival memory survives a restart: records come back exactly, and ids are never reused."""
    path = str(tmp_path / "archival.sqlite3")
    facts = [
        ArchivalRecord("a001", "ava prefers 简体中文 docs ✓\nand terse replies ", ("prefs", "lang:zh-Hans,en"), "s7", 21),
        ArchivalRecord("a002", "deploy target is aws lambda in us-east-1", (), "s8", 12),
        ArchivalRecord("a003", "the eval suite runs nightly", ("ops", "evals"), "s8", 40),
    ]
    archive = SqliteArchive(path)
    for fact in facts:
        rid = archive.insert(fact.text, tags=fact.tags, session_id=fact.session_id, turn_id=fact.turn_id)
        assert rid == fact.rid, "ids are a001, a002, ... in insertion order"
    peek = SqliteArchive(path)
    assert peek.records() == facts, (
        "another connection sees every insert as soon as insert returns, exactly as it went in"
    )
    peek.close()
    archive.close()

    reopened = SqliteArchive(path)
    assert reopened.records() == facts, "records come back exactly after a reopen"
    assert [(type(r.session_id), type(r.turn_id)) for r in reopened.records()] == [(str, int)] * 3, (
        "session_id comes back a str and turn_id an int"
    )
    assert reopened.get("a002") == facts[1]
    assert reopened.search("deploy target", top_k=3) == [(2 / 7, facts[1])], "search works after a reopen"
    reopened.delete("a003")
    with pytest.raises(KeyError):
        reopened.get("a003")
    with pytest.raises(KeyError):
        reopened.delete("a003")
    assert reopened.search("eval suite", top_k=3) == [], "a deleted record is gone from search"
    reopened.close()

    again = SqliteArchive(path)
    rid = again.insert("the eval suite runs at 2am utc", tags=("ops",), session_id="s9", turn_id=3)
    assert rid == "a004", "a deleted id is never handed out again: old answers cite it"
    again.delete("a002")
    rid = again.insert("deploys go through an api gateway", session_id="s9", turn_id=4)
    assert rid == "a005", "a deleted id is never handed out again: old answers cite it"
    again.close()
    last = SqliteArchive(path)
    assert [r.rid for r in last.records()] == ["a001", "a004", "a005"], "a deleted record stays deleted after a reopen"
    last.close()

    many_path = str(tmp_path / "many.sqlite3")
    many = SqliteArchive(many_path)
    for i in range(1001):
        many.insert(f"note {i}", session_id="s1", turn_id=i)
    many.close()
    many = SqliteArchive(many_path)
    assert [r.rid for r in many.records()[-4:]] == ["a998", "a999", "a1000", "a1001"], (
        "ids keep counting past a999, and records come back in insertion order"
    )
    many.close()


TINY = [
    ArchivalRecord("a001", "drift drift tool"),
    ArchivalRecord("a002", "tool chains"),
    ArchivalRecord("a003", ""),
    ArchivalRecord("a004", "Tool chains drift, over many steps"),
    ArchivalRecord("a005", "chains tool"),
]

FACTS = [
    "ava is building a retrieval bot with 12 tools for the sales team",
    "long-horizon tool chains drift after 20 steps in the bfcl v4 benchmark",
    "the user is ava",
    "the deploy target for the agent fleet is aws lambda in us-east-1 behind an api gateway",
    "the eval suite runs nightly at 2am utc on the staging cluster",
    "it is what it is",
    "ava prefers terse replies and dark mode in every dashboard",
    "the sales team works in salesforce and slack",
    "the plan is to ship the bot to the sales team in q3",
    "memory rot is when old facts drown retrieval",
    "sleep-time compute consolidates memory in the background",
    "the team is small",
]

CASES = [
    ("what is the deploy target", {"a004"}),
    ("when does the eval suite run", {"a005"}),
    ("what replies does ava prefer", {"a007"}),
    ("how many tools does the retrieval bot have", {"a001"}),
    ("is the sales team on slack", {"a008"}),
    ("why do tool chains drift", {"a002"}),
    ("what is memory rot", {"a010"}),
    ("what is ava building and what does she prefer", {"a001", "a007"}),
    ("which cloud do we use", {"a004"}),
]


def bm25_term(n: int, tf: int, dl: int, *, N: int, avgdl: float) -> float:
    """One query token's share of a BM25 score, with k1 = 1.2 and b = 0.75."""
    idf = math.log(1 + (N - n + 0.5) / (n + 0.5))
    return idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * dl / avgdl))


@pytest.mark.skip("Part 3")
def test_bm25_recall() -> None:
    """BM25 over archival records, then recall@k against the token-overlap baseline."""
    tiny = BM25(TINY)

    def term(n: int, tf: int, dl: int) -> float:
        return bm25_term(n, tf, dl, N=5, avgdl=13 / 5)

    hits = tiny.search("drift", top_k=10)
    assert [r.rid for _, r in hits] == ["a001"], (
        "only records that contain a query token come back, split like the archive's: 'drift,' is not 'drift'"
    )
    assert [s for s, _ in hits] == pytest.approx([term(1, 2, 3)]), (
        "scores follow the docstring: tf counts repeats, and N and avgdl count every record, the empty one too"
    )
    assert [s for s, _ in tiny.search("drift drift", top_k=10)] == pytest.approx([2 * term(1, 2, 3)]), (
        "a token repeated in the query counts twice"
    )
    hits = tiny.search("tool", top_k=10)
    assert [r.rid for _, r in hits] == ["a002", "a005", "a001", "a004"], (
        "a token found in most records still scores above zero; equal scores keep their order"
    )
    assert [s for s, _ in hits] == pytest.approx([term(4, 1, 2), term(4, 1, 2), term(4, 1, 3), term(4, 1, 6)])
    flipped = BM25(TINY[::-1]).search("tool")
    assert [r.rid for _, r in flipped] == ["a005", "a002", "a001", "a004"], (
        "equal scores keep the order of the list BM25 was built from"
    )
    hits = tiny.search("many steps chains", top_k=2)
    assert [r.rid for _, r in hits] == ["a004", "a002"], "at most top_k results"
    assert [s for s, _ in hits] == pytest.approx([term(1, 1, 6) * 2 + term(3, 1, 6), term(3, 1, 2)])
    one = BM25([ArchivalRecord("a001", "tool chains drift")]).search("drift")
    assert [s for s, _ in one] == pytest.approx([math.log(4 / 3)]), "one record: avgdl is its own length"
    assert BM25([]).search("drift") == [] and BM25([ArchivalRecord("a001", " ")]).search("drift") == []

    store = ArchivalStore()
    for turn, fact in enumerate(FACTS, start=1):
        store.insert(fact, session_id="s3", turn_id=turn)
    bm25 = BM25(store.records())
    query = "what is the deploy target"
    assert (store.search(query, 1)[0][1].rid, bm25.search(query, 1)[0][1].rid) == ("a006", "a004"), (
        "idf outweighs common words that token overlap counts like any other"
    )
    assert recall_at_k(store.search, CASES, 1) == pytest.approx(4 / 9), (
        "recall@k looks at the first k results, averaged over every case"
    )
    assert recall_at_k(bm25.search, CASES, 1) == pytest.approx(7 / 9)
    assert recall_at_k(store.search, CASES, 3) == pytest.approx(6.5 / 9), (
        "a case's recall is the fraction of its relevant records found"
    )
    assert recall_at_k(bm25.search, CASES, 3) == pytest.approx(8 / 9)
    assert recall_at_k(store.search, CASES, 5) == pytest.approx(8 / 9), (
        "recall@k reads the first k results of search(query, k)"
    )
    plan = ("what is the plan for the bot", {"a001", "a009"})
    assert recall_at_k(bm25.search, [plan], 1) == pytest.approx(1 / 2), (
        "one of two relevant records found is a recall of 1/2, also when k is 1"
    )
    for cases in ([CASES[0], ("deploy target", set())], []):
        with pytest.raises(ValueError):
            recall_at_k(bm25.search, cases, 3)


CONVO = [
    ("user", "my name is ava and I ship agents for a living"),
    ("assistant", "noted. what are you building right now?"),
    ("user", "a retrieval bot for our sales org"),
    ("assistant", "plan for drift past twenty steps"),
    ("user", "ok"),
    ("user", "it has twelve tools and a slack front end for the reps"),
    ("assistant", "then log every tool call with its turn"),
    ("user", "remind me what my name is and what I said about the tools"),
    ("user", "thanks"),
]


@pytest.mark.skip("Part 4")
def test_pager_stream() -> None:
    """Messages stream in; the pager warns, pages out and summarizes as it goes, one NDJSON line per event."""
    ctx = MainContext(max_tokens=40)
    tools = MemoryTools(ctx, ArchivalStore(), session_id="s9")
    log: list[str] = []
    calls: list[tuple[str, list[int]]] = []
    pulled: list[int] = []
    between: list[int] = []
    first_page_out: list[int] = []

    async def summarize(previous: str, paged: list) -> str:
        log.append("summarize")
        calls.append((previous, [m.turn for m in paged]))
        await asyncio.sleep(0)
        notes = [" ".join(m.text.split()[:4]) for m in paged]
        return " ".join((previous + " " + " ".join(notes)).split()[-12:])

    async def arrivals():
        for i, message in enumerate(CONVO):
            if i:
                between.append(ctx.tokens())
            pulled.append(i)
            yield message

    async def drive() -> list[str]:
        lines = []
        async for line in page_stream(arrivals(), ctx, summarize, warn_tokens=28):
            lines.append(line)
            event = json.loads(line)
            log.append(event["event"])
            if event["event"] == "page_out" and not first_page_out:
                first_page_out.append(len(pulled))
            if event["event"] == "memory_pressure":
                # The agent's turn: save the oldest message before it can leave the context.
                oldest = ctx.messages[0]
                assert oldest.turn < event["turn"], "memory_pressure comes before anything is paged out"
                tools.archival_memory_insert(oldest.text)
        return lines

    lines = asyncio.run(drive())
    events = [json.loads(line) for line in "".join(lines).splitlines()]
    assert events == [
        {"event": "memory_pressure", "turn": 3, "tokens": 35},
        {"event": "page_out", "turns": [1], "freed": 15},
        {"event": "summary", "tokens": 6, "text": "my name is ava"},
        {"event": "page_out", "turns": [2, 3], "freed": 20},
        {"event": "summary", "tokens": 16, "text": "my name is ava noted. what are you a retrieval bot for"},
        {"event": "page_out", "turns": [4], "freed": 8},
        {"event": "summary", "tokens": 16, "text": "noted. what are you a retrieval bot for plan for drift past"},
        {"event": "page_out", "turns": [5, 6], "freed": 18},
        {"event": "summary", "tokens": 16, "text": "retrieval bot for plan for drift past ok it has twelve tools"},
        {"event": "memory_pressure", "turn": 8, "tokens": 44},
        {"event": "page_out", "turns": [7], "freed": 11},
        {"event": "summary", "tokens": 16, "text": "for drift past ok it has twelve tools then log every tool"},
    ], "warn once per crossing, page out only until it fits, and count the summary in the budget"
    assert first_page_out == [4], "report each event as soon as it happens"
    assert calls == [
        ("", [1]),
        ("my name is ava", [2, 3]),
        ("my name is ava noted. what are you a retrieval bot for", [4]),
        ("noted. what are you a retrieval bot for plan for drift past", [5, 6]),
        ("retrieval bot for plan for drift past ok it has twelve tools", [7]),
    ], "each summary folds the newly paged-out messages into the previous summary"
    assert all(log[i - 1] == "page_out" for i, entry in enumerate(log) if entry == "summarize"), (
        "page_out is reported as soon as messages leave, before the summary is written"
    )
    assert max(between + [ctx.tokens()]) <= 40, "the context fits max_tokens again before the next message"
    assert [m.turn for m in ctx.recall] == [1, 2, 3, 4, 5, 6, 7], "paged-out messages move to recall"
    assert [m.turn for m in ctx.messages] == [8, 9]
    assert ctx.summary == "for drift past ok it has twelve tools then log every tool"
    assert tools.conversation_search("slack front end") == (
        "t6 user: it has twelve tools and a slack front end for the reps"
    ), "summarized messages stay searchable in recall"
    assert tools.archival_memory_search("log every tool call", top_k=1) == (
        "a002 [s9#8] then log every tool call with its turn"
    ), "a fact saved on memory_pressure is cited to the turn that raised it"

    edge = MainContext(max_tokens=10)

    async def feed():
        yield "user", "one two three four"
        yield "user", "a pasted log line that is far longer than the whole budget allows"

    async def first_lines(limit: int) -> list[str]:
        agen = page_stream(feed(), edge, summarize, warn_tokens=6)
        lines = []
        async for line in agen:
            lines.append(line)
            if len(lines) == limit:
                break
        await agen.aclose()
        return lines

    assert [json.loads(line) for line in asyncio.run(first_lines(6))] == [
        {"event": "memory_pressure", "turn": 1, "tokens": 6},
        {"event": "page_out", "turns": [1], "freed": 6},
        {"event": "summary", "tokens": 6, "text": "one two three four"},
    ], "reaching warn_tokens is pressure; once only the newest message is left, the pager moves on"
    assert [m.turn for m in edge.messages] == [2], (
        "the newest message stays, even when it alone is over budget"
    )


SCHEMA = {
    "persona": {"limit": 60},
    "human": {
        "limit": 48,
        "sections": {
            "profile": {
                "limit": 34,
                "sections": {
                    "name": {"limit": 12},
                    "contact": {"limit": 20, "sections": {"email": {"limit": 20}, "slack": {"limit": 12}}},
                },
            },
            "preferences": {"limit": 40},
        },
    },
    "project": {"limit": 40, "sections": {"goal": {"limit": 40}}},
}


@pytest.mark.skip("Part 5")
def test_typed_core() -> None:
    """Core memory as nested, typed sections, each capped in characters."""
    core = TypedCore(SCHEMA)
    assert core.render() == "\n".join(
        [
            "[core]",
            "  persona (0/60)",
            "  human (0/48)",
            "    profile (0/34)",
            "      name (0/12)",
            "      contact (0/20)",
            "        email (0/20)",
            "        slack (0/12)",
            "    preferences (0/40)",
            "  project (0/40)",
            "    goal (0/40)",
        ]
    ), "every section renders in schema order, empty ones included"

    core.append("persona", "the agent remembers user details politely")
    core.append("human.profile.name", "Ava 林小雨")
    core.append("human.profile.contact.email", "ava@example.com")
    core.append("human.profile.contact.slack", "@ava")
    assert core.used("human.profile.name") == 7, "limits count characters, not bytes"
    assert core.used("human") == 26, "a group holds the text of every section anywhere below it"

    before = core.render()
    with pytest.raises(CoreLimitError) as caught:
        core.append("human.profile.contact.slack", "ops")
    error = caught.value
    assert (error.section, error.limit, error.size) == ("human.profile.contact", 20, 23), (
        "the error names the section whose limit is hit, and the size the write would make"
    )
    assert core.render() == before, "a refused write changes nothing"
    with pytest.raises(CoreLimitError) as caught:
        core.append("human.profile.name", "Lindqvist")
    assert caught.value.section == "human.profile.name", "when several limits are hit, name the innermost"
    with pytest.raises(CoreLimitError) as caught:
        core.append("human.profile.name", "Lewis")
    assert (caught.value.section, caught.value.size) == ("human.profile.name", 13), (
        "the space before appended text counts toward the limit"
    )
    with pytest.raises(CoreLimitError) as caught:
        core.append("human.preferences", "terse replies, dark mode, 简体中文 docs")
    assert (caught.value.section, caught.value.limit, caught.value.size) == ("human", 48, 61)
    assert core.render() == before, "a refused write changes nothing"

    core.append("human.preferences", "terse replies, 简体中文")
    with pytest.raises(CoreLimitError) as caught:
        core.append("human.profile.name", "Lin")
    assert (caught.value.section, caught.value.size) == ("human", 49), (
        "every enclosing group is checked, not just the parent"
    )
    core.append("human.profile.name", "Li")
    assert core.used("human") == 48, "a write that lands exactly on a limit fits"
    with pytest.raises(ValueError):
        core.replace("human.profile.contact.email", "a", "4")
    with pytest.raises(ValueError):
        core.replace("human.profile.contact.email", "gmail", "proton")
    with pytest.raises(CoreLimitError):
        core.replace("human.profile.name", "林小雨", "Xiaoyu Lin")
    core.replace("human.profile.contact.email", "@example.com", "@ex.io")
    assert core.text("human.profile.contact.email") == "ava@ex.io"
    for path in ("human.profile.age", "human.profile..name", "persona.tone", "Human"):
        with pytest.raises(KeyError):
            core.append(path, "x")
    with pytest.raises(TypeError):
        core.append("human.profile", "x")

    assert core.render() == "\n".join(
        [
            "[core]",
            "  persona (41/60): the agent remembers user details politely",
            "  human (42/48)",
            "    profile (23/34)",
            "      name (10/12): Ava 林小雨 Li",
            "      contact (13/20)",
            "        email (9/20): ava@ex.io",
            "        slack (4/12): @ava",
            "    preferences (19/40): terse replies, 简体中文",
            "  project (0/40)",
            "    goal (0/40)",
        ]
    ), "render follows the schema at every depth"

    twins = TypedCore({"human": {"limit": 30, "sections": {"name": {"limit": 30}}}, "human_notes": {"limit": 30}})
    twins.append("human_notes", "met at the eval review")
    assert twins.used("human") == 0, "a group holds the text of the sections below it, and nothing else"
