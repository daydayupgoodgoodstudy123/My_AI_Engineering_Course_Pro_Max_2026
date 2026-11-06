import asyncio
import re
import time

import pytest
from memblocks.agents import SleepTimeAgent
from memblocks.archival import Archival
from memblocks.blocks import Block, BlockStore, summarize
from memblocks.consolidate import consolidate, facts
from memblocks.history import BlockLog, Version
from memblocks.lineage import Lineage, Rederive
from memblocks.session import Session


@pytest.mark.skip("Part 1")
def test_block_tools() -> None:
    """Block writes keep to the limit, and a sleep pass frees room fast, even over a big archive."""
    human = Block("human", limit=60, description="facts about the user")
    assert human.append("name=ava") == "human v1 append (8/60)"
    assert human.append("city=Berlin") == "human v2 append (20/60)"
    before = (human.value, human.version, list(human.history))
    assert human.append("role=ships agents for a living in Lisbon").startswith("error:"), (
        "a write that would pass the limit is refused"
    )
    assert (human.value, human.version, human.history) == before, "a refused write changes nothing"
    assert human.replace("", "-").startswith("error:"), "block_replace needs a non-empty old string"
    assert (human.value, human.version, human.history) == before, "a refused write changes nothing"
    assert human.replace("Berlin", "Lisbon") == "human v3 replace (20/60)"
    assert human.append("role=ships agents for a living, at home") == "human v4 append (60/60)", (
        "a write that lands exactly on the limit is accepted"
    )
    assert human.replace("Lisbon", "Lisbon, Portugal").startswith("error:") and human.rewrite("x" * 61).startswith("error:"), (
        "block_replace and rewrites keep to the limit too"
    )
    assert human.replace(", at home", "") == "human v5 replace (51/60)", "block_replace can delete text"

    store = BlockStore()
    task = store.create("task", "the current task scope", limit=100)
    for line in ("plan a 30-lesson agent curriculum", "no paid APIs", "cite arXiv papers", "code in stdlib Python"):
        task.append(line)
    SleepTimeAgent(store, Archival()).run([])
    assert not task.append("deadline=first ten lessons are done by end of May").startswith("error:"), (
        "a sleep pass leaves at least half of a near-limit block free"
    )
    assert task.value == "cite arXiv papers\ncode in stdlib Python\ndeadline=first ten lessons are done by end of May", (
        "the sleep pass keeps the newest whole lines"
    )
    assert summarize("aaa\nbbbb\ncc", 7) == "bbbb\ncc" and summarize("a\nbbbbbbbb\ncc", 5) == "cc", (
        "summarize keeps as many of the newest lines as fit, up to target_len"
    )

    archival = Archival()
    for i in range(32_000):
        archival.insert(f"user{i} lives in Berlin" if i % 4 == 0 else f"user{i} prefers tea", at=float(i))
    sleep = SleepTimeAgent(BlockStore(), archival)
    start = time.perf_counter()
    sleep.run([("lives in berlin", "the users moved to Lisbon")])
    elapsed = time.perf_counter() - start
    assert len(archival.all_records()) == 32_000 and len(archival.valid_records()) == 24_000, (
        "contradicted records are invalidated and kept for audit"
    )
    assert archival.get("a001").reason == "the users moved to Lisbon", "an invalidated record says why"
    assert elapsed < 0.08, "a sleep pass must stay fast on a big archive"


TRICKY = 'says "hi" \\ tab\there\nCRLF\r\nemoji 🧠, LS \u2028 NEL \x85 end '


@pytest.mark.skip("Part 2")
def test_version_log(tmp_path) -> None:
    """Every block version is one line in that block's log, comes back exactly, and survives a torn write."""
    root = tmp_path / "blocks"
    human = Block("human", limit=200, description="facts about the user")
    persona = Block("persona", limit=200, description="the agent's self-concept")
    log = BlockLog(root)
    for block, op, args in (
        (human, "append", ("name=ava 🧠",)),
        (persona, "append", (TRICKY,)),
        (human, "append", ("city=Berlin",)),
        (human, "replace", ("Berlin", "Lisbon")),
        (persona, "rewrite", ("",)),
    ):
        getattr(block, op)(*args)
        log.record(block.label, block.version, op, block.value)
    assert sorted(p.name for p in root.iterdir()) == ["human.log", "persona.log"], "one log file per block"
    assert (root / "persona.log").read_bytes().count(b"\n") == 2, "one line per version"
    for label, version, op in (
        ("human", 5, "append"),
        ("human", 3, "append"),
        ("human", 4, "delete"),
        ("../human", 1, "append"),
        ("human/../persona", 1, "append"),
    ):
        with pytest.raises(ValueError):
            log.record(label, version, op, "pet=cat")

    reopened = BlockLog(root)
    with pytest.raises(ValueError):
        reopened.record("persona", 1, "append", "tone=terse")
    assert reopened.restore("persona", limit=200, description="the agent's self-concept") == persona, (
        "a block comes back exactly after a reopen"
    )
    assert reopened.restore("human", limit=200, description="facts about the user") == human, (
        "a block comes back exactly after a reopen"
    )
    assert reopened.versions("human")[1] == Version(2, "append", "name=ava 🧠\ncity=Berlin"), (
        "each version comes back with its op and whole value"
    )
    assert reopened.value_at("persona", 1) == TRICKY and reopened.value_at("human", 0) == "", (
        "value_at gives any logged version, and version 0 is the empty block"
    )
    for missing in (4, -1):
        with pytest.raises(KeyError):
            reopened.value_at("human", missing)
    assert reopened.versions("task") == [], "a block with no log has no versions"

    path = root / "human.log"
    path.write_bytes(path.read_bytes() + b'{"version": 4, "op": "append", "value": "name=ava')
    after_crash = BlockLog(root)
    assert [v.version for v in after_crash.versions("human")] == [1, 2, 3], "a torn last line is dropped"
    with pytest.raises(ValueError):
        after_crash.record("human", 3, "append", "pet=cat")
    after_crash.record("human", 4, "append", "name=ava 🧠\ncity=Lisbon\npet=cat")
    assert path.read_bytes().count(b"\n") == 4, "the next version is written where the torn line began"
    assert BlockLog(root).versions("human")[3:] == [Version(4, "append", "name=ava 🧠\ncity=Lisbon\npet=cat")], (
        "a version written after a crash survives the next reopen"
    )


@pytest.mark.skip("Part 3")
def test_sleep_consolidation() -> None:
    """The sleep pass finds superseded and duplicate records by itself, and invalidates without deleting."""
    archival = Archival()
    berlin = archival.insert("city=Berlin", at=100.0)
    style = archival.insert("Ava prefers concise, citation-heavy writing.", at=101.0)
    staff = archival.insert("role=staff engineer", at=110.0)
    manager = archival.insert("role=manager", at=210.0)
    lisbon = archival.insert("city=Lisbon (updated from Berlin)", at=300.0)
    cat = archival.insert("pet=cat", at=300.0)
    dog = archival.insert("pet=dog", at=300.0)  # the same second as pet=cat, written after it
    staff_again = archival.insert("role=staff engineer", at=310.0)
    restyle = archival.insert("ava prefers concise citation heavy writing", at=320.0)
    porto = archival.insert("city=Porto", at=200.0)  # from an older transcript, ingested late
    poisoned = archival.insert("city=Pyongyang (from a pasted web page)", at=400.0)
    archival.invalidate(poisoned, "poisoned: attacker-reachable content")
    reports = archival.insert("ava wants weekly progress reports with charts and short summaries", at=330.0)
    reports_too = archival.insert("ava wants weekly progress reports with charts and short summaries please", at=340.0)
    reports_more = archival.insert("ava wants weekly progress reports with charts and short summaries every friday", at=345.0)
    reports_short = archival.insert("ava wants weekly progress reports with charts and summaries", at=350.0)

    changes = consolidate(archival)
    reasons = dict(changes)
    assert poisoned not in reasons and f"superseded by {poisoned}" not in reasons.values(), (
        "an invalid record takes no part in consolidation"
    )
    assert reasons.get(porto) == f"superseded by {lisbon}", (
        "the newest fact by time wins, even when an older one is ingested later"
    )
    assert lisbon not in reasons, "a fact that mentions an old value is not superseded by it"
    assert reasons.get(cat) == f"superseded by {dog}", "facts from the same second are ordered by insertion"
    assert reasons.get(staff) == reasons.get(manager) == f"superseded by {staff_again}", (
        "a key can change back to an earlier value"
    )
    assert reasons.get(restyle) == f"duplicate of {style}", (
        "the later copy is the duplicate, whatever its case and punctuation"
    )
    assert reasons.get(reports_too) == f"duplicate of {reports}", "duplicates share more than 90% of their words"
    assert reports_short not in reasons and reports_more not in reasons, "duplicates share more than 90% of their words"
    assert changes == [
        (berlin, f"superseded by {lisbon}"),
        (staff, f"superseded by {staff_again}"),
        (manager, f"superseded by {staff_again}"),
        (cat, f"superseded by {dog}"),
        (restyle, f"duplicate of {style}"),
        (porto, f"superseded by {lisbon}"),
        (reports_too, f"duplicate of {reports}"),
    ], "changes are reported once each, in insertion order"
    assert facts(archival) == {"city": "Lisbon", "pet": "dog", "role": "staff engineer"}, (
        "every key has the value of its newest valid fact, without the note"
    )
    stale = archival.get(berlin)
    assert len(archival.all_records()) == 15 and (stale.text, stale.valid) == ("city=Berlin", False), (
        "consolidation invalidates, it never deletes"
    )
    assert archival.get(poisoned).reason == "poisoned: attacker-reachable content", "an invalid record keeps its first reason"
    assert consolidate(archival) == [], "a second pass finds nothing new"


def merge_facts(value: str) -> str:
    """The scripted sleep-time model: one line per key, the latest value wins, in first-seen order."""
    latest: dict[str, str] = {}
    for line in value.split("\n"):
        latest[line.split("=", 1)[0]] = line
    return "\n".join(latest.values())


DIFF_FROM = re.compile(r"--- ([a-z_]+)@v(\d+)")
DIFF_TO = re.compile(r"\+\+\+ ([a-z_]+)@v(\d+) \((primary|sleep-time)\)")
HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def replay(trace: str, blocks: dict[str, tuple[int, str]]) -> list[tuple[str, int, str]]:
    """Apply a stream of unified diffs to each block's (version, value), as an operator's tool would."""
    lines = trace.split("\n")
    assert lines.pop() == "", "every line of the trace ends with a newline"
    changes = []
    i = 0
    while i < len(lines):
        head = DIFF_FROM.fullmatch(lines[i])
        to = DIFF_TO.fullmatch(lines[i + 1]) if i + 1 < len(lines) else None
        assert head and to and head[1] == to[1], (
            f"a diff starts with ---/+++ headers naming the block, its versions and the writer: {lines[i]!r}"
        )
        label, old, new = head[1], int(head[2]), int(to[2])
        version, value = blocks[label]
        assert (old, new) == (version, version + 1), "each diff goes from the block's last version to the next"
        src, out, pos = value.split("\n") if value else [], [], 0
        i += 2
        while i < len(lines) and lines[i].startswith("@@"):
            hunk = HUNK.fullmatch(lines[i])
            assert hunk, f"bad hunk header {lines[i]!r}"
            removed, added = int(hunk[2] or 1), int(hunk[4] or 1)
            start = int(hunk[1]) - (1 if removed else 0)
            out += src[pos:start]
            pos = start
            i += 1
            while removed or added:
                tag, text = lines[i][:1], lines[i][1:]
                if tag in (" ", "-"):
                    assert pos < len(src) and src[pos] == text, "a diff applies to the version before it"
                    pos += 1
                    removed -= 1
                if tag in (" ", "+"):
                    out.append(text)
                    added -= 1
                i += 1
        blocks[label] = (new, "\n".join(out + src[pos:]))
        changes.append((label, new, to[3]))
    return changes


@pytest.mark.skip("Part 4")
def test_sleep_alongside_turns() -> None:
    """Turns never wait for the sleep-time agent, its rewrites are compare-and-swap, and every change is a diff."""
    calls: list[tuple[str, str]] = []
    running = [0, 0]  # model calls in flight now, and at most

    async def scenario():
        release, called = asyncio.Event(), asyncio.Event()

        async def model(label: str, value: str) -> str:
            calls.append((label, value))
            running[0] += 1
            running[1] = max(running)
            called.set()
            await release.wait()
            for _ in range(3):  # a real model call takes a few turns of the event loop
                await asyncio.sleep(0)
            running[0] -= 1
            return merge_facts(value)

        async def within(step, message="a primary turn never waits for the sleep-time agent"):
            try:
                return await asyncio.wait_for(step, 1.0)
            except asyncio.TimeoutError:
                pass
            pytest.fail(message)

        store = BlockStore()
        human = store.create("human", "facts about the user", limit=60)
        task = store.create("task", "the current task scope", limit=60)
        persona = store.create("persona", "the agent's self-concept", limit=60)
        human.append("name=ava")
        human.append("city=Berlin")
        task.append("plan=30 lessons")
        start = {label: (store.get(label).version, store.get(label).value) for label in store.labels()}
        session = Session(store, model)

        assert await within(session.turn([("block_append", "human", "city=Lisbon")])) == ["human v3 append (32/60)"], (
            "a turn returns one observation per write"
        )
        assert len(session.trace) == 1, "a write is in the trace as soon as its turn returns"
        await within(called.wait(), "the sleep-time agent starts on a changed block without waiting for idle()")
        await within(session.turn([
            ("block_append", "human", "pet=cat"),
            ("block_append", "persona", "tone=terse"),
            ("block_append", "task", "plan=40 lessons"),
        ]))
        refused = await within(session.turn([("block_append", "human", "x" * 40), ("block_append", "scratch", "x")]))
        assert [obs.startswith("error:") for obs in refused] == [True, True], (
            "a write over the limit or to an unknown block is an error observation"
        )
        assert len(session.trace) == 4, "a refused write leaves no trace"
        assert not session.rewrite("human", "name=ava", expected_version=3), "a rewrite from a stale read is refused"
        assert (human.version, len(session.trace)) == (4, 4), "a refused rewrite changes nothing"
        release.set()
        await within(session.idle(), "idle() returns once the sleep-time agent has nothing left")
        assert task.value == "plan=40 lessons", "idle() waits until every queued block is consolidated"
        await within(session.turn([
            ("block_append", "task", "plan=45 lessons"),
            ("block_append", "persona", "tone=warm"),
        ]))
        await within(session.idle(), "idle() returns once the sleep-time agent has nothing left")
        assert (task.value, persona.value) == ("plan=45 lessons", "tone=warm"), (
            "blocks changed after idle() are consolidated too"
        )
        return start, store, session.trace

    start, store, trace = asyncio.run(scenario())
    human, task = store.get("human"), store.get("task")
    assert "pet=cat" in human.value, "a sleep-time rewrite never drops a write it did not see"
    assert human.value == "name=ava\ncity=Lisbon\npet=cat", "a refused rewrite is retried from a fresh read"
    assert running[1] == 1, "the sleep-time agent works on one block at a time"
    assert calls == [
        ("human", "name=ava\ncity=Berlin\ncity=Lisbon"),
        ("human", "name=ava\ncity=Berlin\ncity=Lisbon\npet=cat"),
        ("persona", "tone=terse"),
        ("task", "plan=30 lessons\nplan=40 lessons"),
        ("task", "plan=40 lessons\nplan=45 lessons"),
        ("persona", "tone=terse\ntone=warm"),
    ], "blocks go in the order turns changed them; a block already queued or being consolidated is not queued again"
    blocks = dict(start)
    changes = replay("".join(trace), blocks)
    assert changes == [
        ("human", 3, "primary"),
        ("human", 4, "primary"),
        ("persona", 1, "primary"),
        ("task", 2, "primary"),
        ("human", 5, "sleep-time"),
        ("task", 3, "sleep-time"),
        ("task", 4, "primary"),
        ("persona", 2, "primary"),
        ("task", 5, "sleep-time"),
        ("persona", 3, "sleep-time"),
    ], "one diff per committed change, in commit order"
    assert blocks == {label: (store.get(label).version, store.get(label).value) for label in blocks}, (
        "replaying the trace rebuilds every block"
    )


@pytest.mark.skip("Part 5")
def test_lineage_invalidation() -> None:
    """When a source goes stale, everything consolidated from it goes too, in an order it can be rebuilt."""
    archival = Archival()
    lineage = Lineage(archival)
    city = archival.insert("city=Berlin", at=1.0)
    role = archival.insert("role=ships_agents", at=2.0)
    style = archival.insert("prefers concise writing", at=3.0)
    profile = lineage.derive("ava ships agents from Berlin", [city, role], at=10.0)
    voice = lineage.derive("write tersely for a Berlin engineer", [profile, style], at=11.0)
    commute = lineage.derive("ava cycles to work in Berlin", [city], at=12.0)
    weekly = lineage.derive("weekly plan around Berlin meetups", [profile, commute], at=13.0)
    brief = lineage.derive("brief: terse notes on Berlin time", [voice, city], at=4.0)  # stamped with the time it covers
    notes = lineage.derive("style notes", [style], at=15.0)
    with pytest.raises(KeyError):
        lineage.derive("orphan", ["a999"], at=16.0)
    assert len(archival.all_records()) == 9, "a derive that raises stores nothing"

    moved = "the user moved to Lisbon"
    out = lineage.invalidate(city, moved)
    assert [r.rid for r in out] == [profile, voice, commute, weekly, brief], (
        "every record made from the stale one, once each, sources before the records made from them"
    )
    assert [r.chain for r in out] == [
        (city, profile),
        (city, profile, voice),
        (city, commute),
        (city, profile, weekly),
        (city, brief),
    ], "each chain is the shortest path of derivations, ties through the earlier source"
    assert all(r.reason == moved for r in out), "each entry carries the stale record's reason"
    assert [archival.get(r.rid).reason for r in out] == [f"derived from {r.chain[-2]}" for r in out], (
        "each record is invalidated through the record before it on its chain"
    )
    assert archival.get(notes).valid and archival.get(role).valid and archival.get(style).valid, (
        "records not made from the stale one stay valid"
    )
    assert lineage.invalidate(city, "again") == [] and lineage.invalidate(profile, "again") == [], (
        "invalidating again changes nothing"
    )
    assert archival.get(city).reason == moved, "an invalid record keeps its first reason"

    pet = archival.insert("pet=cat", at=20.0)
    owner = lineage.derive("ava has a cat", [pet], at=21.0)
    owner_copy = lineage.derive("Ava has a cat.", [pet], at=22.0)
    vet = lineage.derive("book the cat's yearly vet visit", [owner_copy], at=24.0)
    food = lineage.derive("buy cat food every week", [owner], at=23.0)
    budget = lineage.derive("monthly budget for the vet visit and cat food", [food, vet], at=25.0)
    dog = archival.insert("pet=dog", at=30.0)
    assert consolidate(archival) == [(pet, f"superseded by {dog}"), (owner_copy, f"duplicate of {owner}")], (
        "Part 3's consolidation runs on this archive too"
    )
    out = lineage.invalidate(pet, "recheck")
    assert [r.rid for r in out] == [owner, vet, food, budget], (
        "records made from a source that consolidation invalidated are caught too"
    )
    assert [r.chain for r in out] == [
        (pet, owner),
        (pet, owner_copy, vet),
        (pet, owner, food),
        (pet, owner_copy, vet, budget),
    ], "each chain is the shortest path of derivations, ties through the earlier source"
    assert out == [Rederive(r.rid, r.chain, f"superseded by {dog}") for r in out], (
        "each entry carries the stale record's reason as the archive holds it"
    )

    rolling = Archival()
    sessions = Lineage(rolling)
    first = rolling.insert("session 0 transcript", at=0.0)
    summary = sessions.derive("summary of session 0", [first], at=0.5)
    for i in range(1, 1500):
        transcript = rolling.insert(f"session {i} transcript", at=float(i))
        summary = sessions.derive(f"summary through session {i}", [summary, transcript], at=i + 0.5)
    out = sessions.invalidate(first, "transcript redacted")
    assert len(out) == 1500 and out[-1].rid == summary and len(out[-1].chain) == 1501, (
        "a long chain of rolling summaries comes back whole, in creation order"
    )
