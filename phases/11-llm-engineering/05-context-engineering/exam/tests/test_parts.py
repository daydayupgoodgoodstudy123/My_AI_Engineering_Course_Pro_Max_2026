import asyncio
import copy
import json
import time

import pytest
from contextloom.models import Component, ScoredDocument, Exchange
from contextloom.service import ContextService, ContextSession
from contextloom.budget import ContextBudget, assemble_priority
from contextloom.history import compress_history
from contextloom.primitives import count_tokens
from contextloom.store import ComponentLog
from contextloom.codec import encode_component
from contextloom.placement import zigzag_documents
from contextloom.stream import stream_revisions
from contextloom.documents import DocumentNode
from contextloom.digest import digest_document

@pytest.mark.skip("Part 1")
def test_context_preview_and_budget():
    """Repair paired context selection, slot updates and compulsory allocations."""
    docs = [Component(key, "retrieved", key + " text", 1) for key in ("drop", "z", "a")]
    selected = ContextService().preview(docs, [0.1,0.9,0.8], 0.5)
    assert [(item.component.key, item.score) for item in selected] == [("z",0.9),("a",0.8)], "selected documents retain their corresponding relevance scores"
    assert docs[0].key == "drop" and len(docs) == 3, "preview leaves the source document sequence untouched"
    budget = ContextBudget(15, 3)
    budget.allocate("retrieved", "old " * 6)
    budget.allocate("history", "two words")
    replacement = "new one two three four five six"
    assert budget.allocate("retrieved", replacement) == replacement, "replacing a slot uses only its final contribution to the budget"
    report = budget.report()
    assert report["used"] == 11 and report["remaining"] == 1, "replacement accounting agrees with the complete live slot state"
    assert list(report["contents"]) == ["retrieved","history"], "slot replacement preserves its first position"
    compulsory = assemble_priority("system rule", "answer this query now", [("history", "history " * 20)], 14, 3)
    assert compulsory["contents"]["query"] == "answer this query now" and compulsory["contents"]["system"] == "system rule", "compulsory query and system remain complete under optional pressure"
    assert compulsory["used"] + compulsory["reserve"] <= 14 and list(compulsory["contents"]) == ["system","history","query"], "allocation priority and final message layout satisfy the declared window"
    short = compress_history([Exchange("one", "u", "a")], 7)
    assert short["tokens"] == 7 and short["text"] == "[Recent Conversation]\nuser: u\nassistant: a", "history estimates include role labels and section headers in the rendered text"
    pairs = [Exchange(f"e{i}", "one two three four", "five six seven eight") for i in range(5)]
    compressed = compress_history(pairs, 50)
    assert compressed["retained"] == tuple(pairs[-2:]) and compressed["summary_sources"] == ("e0","e1","e2"), "compression preserves whole recent exchanges and every summarized source"
    assert compressed["tokens"] == count_tokens(compressed["text"]) <= 50 and compressed["summary"], "the rolling summary participates in the complete history budget"
    assert compress_history([], 0) == {"text":"","tokens":0,"retained":(),"summary":"","summary_sources":()}, "empty history consumes no context budget"
    failed = False
    try:
        compress_history(pairs[-2:], 1)
    except ValueError:
        failed = True
    assert failed, "infeasible compulsory recent history is reported rather than silently discarded"
    failed = False
    try:
        assemble_priority("too many words", "also many words", [], 5, 1)
    except ValueError:
        failed = True
    assert failed, "an infeasible compulsory prompt is rejected"
    long_history = [Exchange(f"t{i}", "question " * 24 + f"u{i}", "answer " * 24 + f"a{i}") for i in range(1200)]
    start = time.perf_counter()
    result = compress_history(long_history, 160)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.06, "long transcript compression should stay responsive"
    assert result["retained"] == tuple(long_history[-2:]) and result["summary_sources"] == tuple(f"t{i}" for i in range(1198)), "responsive compression retains every required exchange and provenance update"
    assert result["tokens"] == count_tokens(result["text"]) <= 160 and result["summary"].endswith("a1197"), "responsive compression still returns the current summary and complete rendered accounting"

@pytest.mark.skip("Part 2")
def test_component_revision_replay(tmp_path):
    """Replay exact revisions and checkpointed state in first-seen slot order."""
    path = tmp_path / "components.log"
    log = ComponentLog(path)
    z1 = Component("z", "retrieved", "old source", 1)
    a1 = Component("a", "history", "first\r\nsecond 世界", 1)
    z3 = Component("z", "retrieved", "new source with details", 3, ("doc:β",))
    summary = Component("summary", "summary", "Summary: decision retained", 1, ("turn:2","turn:1"))
    for component in (z1,a1,z3,summary):
        log.append(component)
    expected = [z3,a1,summary]
    assert ComponentLog(path).replay() == expected, "new revisions replace live slots without duplication or name sorting"
    assert ComponentLog(path).replay()[1].text == "first\r\nsecond 世界", "revision replay preserves exact Unicode and CRLF source text"
    assert ComponentLog(path).replay()[2].provenance == ("turn:2","turn:1"), "summary provenance remains separate and ordered rather than inferred from text"
    encoded = [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]
    assert len(encoded) == 4 and all(type(value["tokens"]) is int for value in encoded), "the append log retains integer token estimates for every committed revision"
    assert sum(row.tokens for row in log.replay()) == sum(count_tokens(row.text) for row in expected), "only live revisions contribute tokens and summary text is included"
    before = path.read_bytes()
    failed = False
    try:
        log.append(z1)
    except ValueError:
        failed = True
    assert failed and path.read_bytes() == before, "stale append attempts leave committed revision history unchanged"
    log.checkpoint()
    assert path.read_bytes() == b"" and log.checkpoint_path.exists(), "checkpoint compacts covered revisions into the declared checkpoint file"
    assert ComponentLog(path).replay() == expected, "checkpointed live state survives a new process with an empty log"
    path.write_text(json.dumps(encode_component(z1)) + "\n", encoding="utf-8")
    assert ComponentLog(path).replay() == expected, "covered stale log entries cannot replace newer checkpoint contents"
    # A checkpoint may be visible before covered log entries have been cleared.
    path.write_bytes(before)
    assert ComponentLog(path).replay() == expected, "checkpoint replay tolerates covered older log revisions without reviving them"
    a2 = Component("a", "history", "", 2, ("turn:3",))
    log.append(a2)
    assert ComponentLog(path).replay() == [z3,a2,summary], "post-checkpoint updates preserve existing slot order and empty content"
    conflicting = Component("z", "retrieved", "different payload", 3)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(encode_component(conflicting)) + "\n")
    failed = False
    try:
        log.replay()
    except ValueError:
        failed = True
    assert failed, "the same revision cannot identify conflicting component contents"
    unicode_component = Component("unicode", "history", "left\u2028right\u0085tail", 1, ("source",))
    unicode_log = ComponentLog(tmp_path / "unicode.log")
    unicode_log.append(unicode_component)
    assert ComponentLog(unicode_log.path).replay() == [unicode_component], "Unicode line separators inside text remain part of one revision record"

    equal_log = ComponentLog(tmp_path / "equal-revision.log")
    equal_log.append(z1)
    equal_before = equal_log.path.read_bytes()
    failed = False
    try:
        equal_log.append(z1)
    except ValueError:
        failed = True
    assert failed and equal_log.path.read_bytes() == equal_before, "an appended revision must strictly advance its component without changing committed history"

@pytest.mark.skip("Part 3")
def test_retrieved_block_zigzag():
    """Place ranked retrieved items at opposite ends with stable input ties."""
    items = [ScoredDocument(Component(key, "retrieved", "same text", 1), score) for key,score in [("z",0.9),("b",0.5),("a",0.9),("d",0.2),("e",0.5),("f",0.1)]]
    original = copy.deepcopy(items)
    assert [item.component.key for item in zigzag_documents(items)] == ["z","b","d","f","e","a"], "even retrieved blocks preserve ranked items with the strongest pair at opposite ends"
    assert [item.component.key for item in zigzag_documents(items[:5])] == ["z","b","d","e","a"], "odd retrieved blocks preserve every selected item exactly once"
    assert items == original, "placement leaves scores and source items untouched"
    assert zigzag_documents([]) == [] and zigzag_documents(items[:1]) == items[:1], "empty and single-item retrieved blocks remain well formed"
    assert zigzag_documents([items[3],items[0]]) == [items[0],items[3]], "two-item blocks keep descending relevance at the two ends"
    ties = [ScoredDocument(Component(key, "retrieved", "identical", 1), 0.5) for key in ("z","a","m","b")]
    assert [item.component.key for item in zigzag_documents(ties)] == ["z","m","b","a"], "equal scores retain input rank without comparing key or text"
    service = ContextService()
    report = service.layout("system", "query", items, 100, 9)
    assert list(report["contents"]) == ["system","z","b","d","f","e","a","query"], "zigzag applies inside the retrieved block while system and query keep their fixed layout"
    assert report["contents"]["system"] == "system" and report["contents"]["query"] == "query" and report["reserve"] == 9, "retrieved placement preserves compulsory context and generation reserve"
    tight = service.layout("system", "query", items, 8, 2)
    assert tight["contents"]["query"] == "query" and tight["used"] + tight["reserve"] <= 8, "placement delegates tight-window admission to the repaired budget dependency"

    zero_scores = [ScoredDocument(Component(key, "retrieved", key, 1), score) for key, score in (("zero-z", 0.0), ("best", 1.0), ("zero-a", 0.0))]
    assert [item.component.key for item in zigzag_documents(zero_scores)] == ["best", "zero-a", "zero-z"], "selected zero-score components remain in stable retrieved rank order"

@pytest.mark.skip("Part 4")
def test_context_revision_sse():
    """Emit coherent SSE snapshots per update, preserving incremental source use."""
    updates = [Component("history", "history", "hello\n世界", 1), Component("tools", "tool", "read write", 1), Component("history", "history", "new recent conversation", 2)]
    state = {"pulled":0,"closed":False}
    async def source():
        try:
            for component in updates:
                state["pulled"] += 1
                yield component
        finally:
            state["closed"] = True
    async def collect():
        session = ContextSession("system rule", "current query", 30, 5)
        stream = stream_revisions(source(), session)
        first = await anext(stream)
        assert state["pulled"] == 1, "emit one complete revision before reading another update"
        events = [first] + [event async for event in stream]
        assert state["closed"], "the supplied ownership wrapper closes the update source"
        return events
    events = asyncio.run(collect())
    decoded = []
    for number,event in enumerate(events,1):
        assert event.endswith("\n\n") and event.count("\n\n") == 1, "each SSE revision ends with one blank-line delimiter"
        fields = [line.split(": ",1) for line in event[:-2].split("\n")]
        assert [name for name,value in fields] == ["id","event","data"], "SSE revision fields carry id event type and one JSON data record"
        values = dict(fields)
        assert values["id"] == str(number) and values["event"] == "context", "SSE ids advance with coherent context revisions"
        decoded.append(json.loads(values["data"]))
    assert len(decoded) == 3 and [value["revision"] for value in decoded] == [1,2,3], "each incoming update produces exactly one applied-state revision"
    assert [list(value["contents"]) for value in decoded] == [["system","history","query"],["system","history","tools","query"],["system","history","tools","query"]], "each revision retains the complete admitted context layout"
    assert [value["contents"]["history"] for value in decoded] == ["hello\n世界","hello\n世界","new recent conversation"], "snapshots preserve multiline text and replace the updated slot coherently"
    assert decoded[1]["selected"] == ["system","history","tools","query"] and list(decoded[2]["contents"]) == ["system","history","tools","query"], "selected component ids and contents describe the same ordered state"
    for snapshot in decoded:
        assert snapshot["used"] == sum(snapshot["allocations"].values()) and snapshot["used"] + snapshot["remaining"] + snapshot["reserve"] == 30, "every revision exposes complete internally consistent budget accounting"
    state.update(pulled=0,closed=False)
    async def stop_early():
        stream = stream_revisions(source(), ContextSession("s", "q", 30, 5))
        await anext(stream)
        await stream.aclose()
        assert state["closed"] and state["pulled"] == 1, "client close completes without pulling future updates"
    asyncio.run(stop_early())
    async def empty():
        if False:
            yield updates[0]
    async def collect_empty():
        return [event async for event in stream_revisions(empty(), ContextSession("s","q",30,5))]
    assert asyncio.run(collect_empty()) == [], "empty update sources produce no fabricated context revision"

    assert all(snapshot["reserve"] == 5 for snapshot in decoded), "each streamed snapshot preserves the session generation reserve"
    async def empty_slot_source():
        yield Component("empty-slot", "history", "", 1)
    async def collect_empty_slot():
        return [event async for event in stream_revisions(empty_slot_source(), ContextSession("s", "q", 30, 5))]
    empty_event = asyncio.run(collect_empty_slot())[0]
    empty_snapshot = json.loads(empty_event.split("data: ", 1)[1][:-2])
    assert empty_snapshot["contents"] == {"system":"s","empty-slot":"","query":"q"} and empty_snapshot["allocations"]["empty-slot"] == 0 and empty_snapshot["selected"] == ["system","query"], "empty admitted slots retain their exact content and allocation"

@pytest.mark.skip("Part 5")
def test_bottom_up_document_digest():
    """Digest a supplied section tree bottom-up with ordered source paths."""
    left_leaf = DocumentNode("p", "Paragraph", 2, "one two three four five")
    right_leaf = DocumentNode("p", "Paragraph", 2, "six seven eight nine ten")
    short = DocumentNode("short", "Paragraph", 5, " keep  spacing ")
    root = DocumentNode("root", "Document", 1, children=(DocumentNode("left","Overview",1,children=(left_leaf,)),DocumentNode("right","Overview",1,children=(right_leaf,)),short))
    calls = []
    def summarize(text, budget, path):
        calls.append((path,text,budget))
        return f"D({path[-1]})"
    report = digest_document(root, summarize)
    assert [path for path,text,budget in calls] == [("root","left","p"),("root","right","p"),("root",)], "child digests are completed before the parent is summarized"
    assert calls[-1][1] == "D(p)\nD(p)\n keep  spacing " and calls[-1][2] == 1, "parent summarization consumes its child digests with its own local budget"
    assert report["sources"] == (("root","left","p"),("root","right","p"),("root","short")), "ordered leaf source paths survive repeated section and paragraph titles"
    assert report["children"][0]["title"] == report["children"][1]["title"] == "Overview" and len(report["children"]) == 3, "equal titles do not merge distinct document branches"
    assert report["children"][2]["text"] == " keep  spacing " and ("root","short") not in [path for path,text,budget in calls], "a fitting paragraph remains verbatim without redundant summarization"
    assert report["text"] == "D(root)" and report["tokens"] == 1, "the root digest respects its own declared token budget"
    assert calls[0][2] == calls[1][2] == 2 and left_leaf.text == "one two three four five", "local paragraph budgets and source text remain intact"
    def visit(output,node):
        assert output["tokens"] == count_tokens(output["text"]) <= node.budget, "every document digest reports its actual local token estimate"
        for child,child_node in zip(output["children"],node.children):
            visit(child,child_node)
    visit(report,root)
    calls.clear()
    leaf = DocumentNode("single","Empty",0,"")
    assert digest_document(leaf,summarize)["sources"] == (("single",),) and calls == [], "empty paragraphs still retain their source identity without a summary call"
    failed = False
    try:
        digest_document(left_leaf,lambda text,budget,path: "too many summary words")
    except ValueError:
        failed = True
    assert failed, "over-budget injected summaries cannot silently violate a local digest cap"

    ordered_root = DocumentNode("ordered", "Document", 20, children=(DocumentNode("z", "Paragraph", 5, "z"), DocumentNode("a", "Paragraph", 5, "a")))
    assert digest_document(ordered_root, summarize)["sources"] == (("ordered", "z"), ("ordered", "a")), "leaf provenance follows document order even when source keys sort differently"
