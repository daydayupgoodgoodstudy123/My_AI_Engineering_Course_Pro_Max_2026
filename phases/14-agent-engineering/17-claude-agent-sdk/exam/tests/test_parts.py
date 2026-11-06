import asyncio
import json
import time

import pytest
from harness.batching import Costs, choose_plan, compare_plans
from harness.core import Deny, Harness, Hooks, Tool, ToolRegistry, count_tokens
from harness.fanout import fan_out
from harness.mirror import MirrorStore
from harness.store import SessionStore, Turn
from harness.tree import prune_expired, render_tree


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def context_of(store, session_id: str) -> int:
    return sum(count_tokens(turn.content) for turn in store.load(session_id))


@pytest.mark.skip("Part 1")
def test_harness_dispatch() -> None:
    """Hooks gate and audit every tool call, and subagents keep their context to themselves."""
    wrote: list[str] = []

    def write_file(path: str, text: str) -> str:
        wrote.append(path)
        return f"wrote {len(text)} chars to {path}"

    def read_file(path: str) -> str:
        if path == "missing.txt":
            raise FileNotFoundError(path)
        return f"[content of {path}: 42 lines]"

    tools = ToolRegistry()
    tools.register(Tool("write_file", "write a file", write_file))
    tools.register(Tool("read_file", "read a file", read_file))

    def stay_in_work(session_id: str, tool: str, args: dict):
        if tool == "write_file" and not args["path"].startswith("/work/"):
            return Deny("writes stay under /work")
        return None

    gated: list[str] = []
    audit: list[tuple[str, str, str]] = []
    hooks = Hooks(
        pre_tool_use=[stay_in_work, lambda session_id, tool, args: gated.append(tool)],
        post_tool_use=[lambda session_id, tool, result: audit.append((session_id, tool, result))],
    )
    store = SessionStore()
    harness = Harness(tools, hooks, store, clock=Clock())
    run = harness.run_agent("main", "tidy the repo", [
        ("write_file", {"path": "/etc/hosts", "text": "x"}),
        ("write_file", {"path": "/work/notes.md", "text": "hi"}),
        ("read_file", {"path": "missing.txt"}),
        ("grep", {"pattern": "TODO"}),
    ])
    assert wrote == ["/work/notes.md"], "a denied call must not run the tool"
    assert run.tool_calls[0][2] == "denied: writes stay under /work"
    assert gated == ["write_file", "read_file", "grep"], "PreToolUse hooks after a Deny do not run"
    assert audit[:1] == [("main", "write_file", "denied: writes stay under /work")], (
        "post_tool_use audits denied calls too"
    )
    assert [result for _, _, result in audit] == [
        "denied: writes stay under /work",
        "wrote 2 chars to /work/notes.md",
        "error: FileNotFoundError: missing.txt",
        "error: unknown tool 'grep'",
    ], "post_tool_use sees every result, tool errors included"
    assert run.context_tokens == context_of(store, "main")

    lead = harness.run_agent("lead", "review these three modules", [("read_file", {"path": "plan.md"})])
    before = lead.context_tokens
    subs = harness.spawn_subagents(lead, [
        (f"review module {name}", [("read_file", {"path": f"{name}.py"})] * 3) for name in "abc"
    ])
    assert [s.session_id for s in subs] == ["lead.sub01", "lead.sub02", "lead.sub03"]
    assert store.list_subkeys("lead") == ["lead.sub01", "lead.sub02", "lead.sub03"]
    assert lead.context_tokens == before + sum(count_tokens(s.output) for s in subs), (
        "only subagent results return to the orchestrator"
    )
    assert [t.content for t in store.load("lead")[-3:]] == [s.output for s in subs]
    assert all(s.context_tokens == context_of(store, s.session_id) for s in subs)

    again = harness.run_agent("lead", "now summarize the reviews", [])
    assert again.context_tokens == context_of(store, "lead"), "a resumed session keeps its earlier context"

    calls = [("read_file", {"path": f"src/{i}.py"}) for i in range(5000)]
    start = time.perf_counter()
    long_run = harness.run_agent("scan", "scan every file", calls)
    assert time.perf_counter() - start < 0.12, "run_agent should stay fast on long sessions"
    assert long_run.context_tokens == context_of(store, "scan")


TRICKY = [
    "line one\nline two",
    "naïve café ✓ 🚀",
    "para graph, and a next-line\x85here",
    'tab\tand "quotes" and a \\ backslash',
    "",
    "ends with a newline\n",
]

# (operation, session, argument) applied to both stores, in order
OPS = [
    ("link", "lead", "lead/sub01"),
    ("link", "lead/sub01", "lead/sub01/sub01"),
    ("link", "lead/sub01/sub01", "lead/sub01/sub01/sub01"),
    ("link", "lead", "lead_sub01"),
    ("link", "lead", "lead/sub02"),  # spawned, nothing written yet
    ("append", "lead/sub01", Turn("user", "check module a", 1767225601.5)),
    ("append", "lead/sub01/sub01", Turn("tool", "read_file: [a.py: 42 lines]\n", 0.1 + 0.2)),
    ("append", "lead/sub01/sub01/sub01", Turn("tool", "grep: 3 matches", 4.5)),
    ("append", "lead_sub01", Turn("user", "check module b", 1767225602.25)),
    ("append", "Lead", Turn("user", "a different session", 1.0)),
    ("append", "../escape", Turn("user", "still inside the root", 2.0)),
    ("append", "naïve / id?", Turn("assistant", "done", 3.0)),
]


@pytest.mark.skip("Part 2")
def test_session_mirror(tmp_path) -> None:
    """Sessions are mirrored to JSONL files as they stream, and come back exactly."""
    root = tmp_path / "mirror"
    store = MirrorStore(root)
    memory = SessionStore()
    turns = [Turn("user" if i == 0 else "tool", text, 1767225600.0 + i / 3) for i, text in enumerate(TRICKY)]
    for turn in turns[:3]:
        store.append("lead", turn)
        memory.append("lead", turn)

    text = store.mirror_path("lead").read_text(encoding="utf-8")
    lines = text.split("\n")
    assert lines[-1] == "" and len(lines) == 4, "each turn is on disk, one line each, as soon as it is appended"
    assert [json.loads(line) for line in lines[:-1]] == [
        {"role": t.role, "content": t.content, "ts": t.ts} for t in turns[:3]
    ], "a turn line holds role, content and ts"
    assert "naïve café ✓ 🚀" in text, "the mirror is for people: non-ASCII text is written as it is"

    for turn in turns[3:]:
        store.append("lead", turn)
        memory.append("lead", turn)
    for op, session, arg in OPS:
        for target in (store, memory):
            if op == "link":
                target.link_sub(session, arg)
            else:
                target.append(session, arg)

    ids = memory.list_sessions()
    assert store.list_sessions() == ids, "a session exists once it has a turn or takes part in a link"
    paths = [store.mirror_path(sid) for sid in ids]
    assert all(p.parent == root and p.exists() for p in paths) and len({p.name.lower() for p in paths}) == len(ids), (
        "every session gets its own mirror file inside root"
    )

    reopened = MirrorStore(root)
    assert reopened.list_sessions() == ids, "a reopened store sees every session"
    assert reopened.load("lead") == turns, "a session must round-trip exactly"
    for sid in ids:
        assert reopened.load(sid) == memory.load(sid), f"same turns as SessionStore for {sid!r}"
        assert reopened.list_subkeys(sid) == memory.list_subkeys(sid), f"same subkeys as SessionStore for {sid!r}"
    assert reopened.load("nobody") == []

    lead_mirror = reopened.mirror_path("lead").read_text(encoding="utf-8")
    reopened.delete("lead/sub01")
    memory.delete("lead/sub01")
    reopened.delete("nobody")
    assert reopened.list_sessions() == memory.list_sessions(), "delete cascades to every subagent session below"
    assert not reopened.mirror_path("lead/sub01/sub01").exists(), "a deleted session's mirror file is removed"
    assert reopened.mirror_path("lead").read_text(encoding="utf-8").startswith(lead_mirror), (
        "mirror files are only ever appended to, deletes included"
    )
    assert reopened.list_subkeys("lead") == ["lead_sub01", "lead/sub02"]

    third = MirrorStore(root)
    assert third.list_sessions() == memory.list_sessions()
    assert third.list_subkeys("lead") == ["lead_sub01", "lead/sub02"], (
        "a deleted subagent stays out of its parent's subkeys after a reopen"
    )
    assert third.load("lead") == turns


# quiz Q12: a 50-token prompt and brief, 2,000 tokens read per module, summaries of 100 for one
# module and 300 for five, and 3,000 tokens of system prompt and tool definitions per subagent
Q12 = Costs(prompt=50, brief=50, overhead=3000, summary_base=50, summary_per_task=50)
MODULES = [(f"m{i:02d}.py", 2000) for i in range(1, 21)]
UNEVEN = [("a.py", 100), ("b.py", 100), ("c.py", 400), ("d.py", 400), ("e.py", 100)]


@pytest.mark.skip("Part 3")
def test_batch_plan() -> None:
    """Plan the subagents: what each plan leaves in the orchestrator's context, what it costs, which one to run."""
    names = [name for name, _ in MODULES]
    plans = compare_plans(MODULES, Q12)
    assert [p.batch_size for p in plans] == list(range(21)), "one plan without subagents, then one per batch size"
    alone, one_each, by_five = plans[0], plans[1], plans[5]
    assert (alone.subagents, alone.orchestrator_tokens, alone.total_tokens) == (0, 40050, 40050), (
        "without subagents the orchestrator reads every task itself"
    )
    assert [list(b) for b in plans[3].batches] == [names[i:i + 3] for i in range(0, 20, 3)] and all(
        [name for batch in p.batches for name in batch] == names and all(p.batches) for p in plans[1:]
    ), "tasks are cut in order into batches of k, the last batch taking what is left"
    assert one_each.orchestrator_tokens == 2050, "only the summaries return to the orchestrator"
    assert by_five.orchestrator_tokens == 1250, "a subagent hands back one summary for its whole batch"
    assert (one_each.total_tokens, by_five.total_tokens) == (105050, 54650), (
        "the total adds every subagent's context: overhead, brief, reads and the summary it writes"
    )
    assert list(by_five.subagent_tokens) == [13350] * 4
    assert (plans[3].subagents, plans[3].orchestrator_tokens, plans[3].total_tokens) == (7, 1400, 64100)

    uneven = Costs(prompt=40, brief=10, overhead=100, summary_base=20, summary_per_task=5)
    assert [(p.orchestrator_tokens, list(p.subagent_tokens), p.total_tokens) for p in compare_plans(UNEVEN, uneven)] == [
        (1140, [], 1140),
        (165, [235, 235, 535, 535, 235], 1940),
        (125, [340, 940, 235], 1640),
        (105, [745, 640], 1490),
        (105, [1150, 235], 1490),
        (85, [1255], 1340),
    ], "every plan, for tasks that read different amounts"

    assert choose_plan(MODULES, Q12, cap=40050, window=16000).batch_size == 0, (
        "no subagents is cheapest when the orchestrator can hold every read"
    )
    chosen = choose_plan(MODULES, Q12, cap=40049, window=16000)
    assert chosen.subagents == 4, "the cheapest plan in which every subagent fits its own window"
    assert chosen.batch_size == 5, "equal plans go to the smaller batch"
    with pytest.raises(ValueError):
        choose_plan(MODULES, Q12, cap=1000, window=16000)
    assert choose_plan(UNEVEN, uneven, cap=1000, window=800).batch_size == 3, (
        "a batch size that does not fit says nothing about larger ones"
    )
    free = Costs(prompt=20, brief=0, overhead=0, summary_base=0, summary_per_task=10)
    tied = [("a.py", 30), ("b.py", 10), ("c.py", 10), ("d.py", 30), ("e.py", 10), ("f.py", 10)]
    assert choose_plan(tied, free, cap=100, window=65).batch_size == 2, "equal totals go to fewer subagents"

    tools = ToolRegistry()
    tools.register(Tool("read_file", "read a file", lambda path: f"[content of {path}: 42 lines]"))
    harness = Harness(tools, Hooks(), SessionStore(), clock=Clock())
    lead = harness.run_agent("lead", "review these seven modules", [])
    files = [f"m{i}.py" for i in range(1, 8)]
    brief = "review your modules"
    costs = Costs(
        prompt=lead.context_tokens,
        brief=count_tokens(brief),
        overhead=0,
        summary_base=count_tokens("processed 3 tools; session=lead.sub01"),
        summary_per_task=0,
    )
    read = count_tokens("read_file: [content of m1.py: 42 lines]")
    plan = choose_plan([(f, read) for f in files], costs, cap=40, window=26)
    assert [list(b) for b in plan.batches] == [files[:3], files[3:6], files[6:]]
    subs = harness.spawn_subagents(lead, [(brief, [("read_file", {"path": f}) for f in b]) for b in plan.batches])
    assert lead.context_tokens == plan.orchestrator_tokens, (
        "the orchestrator's context grows by the summaries alone, as planned"
    )
    assert [s.context_tokens for s in subs] == list(plan.subagent_tokens), "each subagent's context holds its own reads"
    assert lead.context_tokens + sum(s.context_tokens for s in subs) == plan.total_tokens


def parse_sse(text: str) -> list[tuple[str, dict]]:
    assert text.endswith("\n\n"), "every event ends with a blank line"
    events = []
    for block in text[:-2].split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.split("\n"):
            name, sep, value = line.partition(": ")
            assert sep and name in ("event", "data") and name not in fields, (
                "an event is one event: line and one data: line"
            )
            fields[name] = value
        events.append((fields.get("event"), json.loads(fields["data"])))
    return events


class Probe:
    """Fake subagents: each awaits for a while, does private work in its own session, and reports."""

    def __init__(self, store: SessionStore, steps: dict[str, int]) -> None:
        self.store = store
        self.steps = steps
        self.active = 0
        self.peak = 0
        self.started: list[str] = []
        self.finished: list[str] = []

    async def __call__(self, session_id: str, prompt: str) -> str:
        self.started.append(session_id)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            self.store.append(session_id, Turn("tool", "read_file: " + "private notes " * 30))
            for _ in range(self.steps[prompt]):
                await asyncio.sleep(0)
            self.finished.append(session_id)
            if prompt == "module 07":
                raise ValueError(f"no tests for {prompt}")
            return f"tests for {prompt} are in tests/test_{prompt[-2:]}.py"
        finally:
            self.active -= 1


@pytest.mark.skip("Part 4")
def test_parallel_subagents() -> None:
    """Twenty subagents, five at a time, each result streamed back as it finishes."""
    tasks = [f"module {i:02d}" for i in range(1, 21)]
    steps = {task: 3 * i for i, task in enumerate(tasks, start=1)}
    steps["module 01"] = 400
    store = SessionStore()
    store.append("lead", Turn("user", "find the test file for each of these 20 modules"))
    probe = Probe(store, steps)

    async def consume() -> tuple[list[str], list[int]]:
        frames, finished_at = [], []
        async for frame in fan_out(store, "lead", tasks, probe, max_parallel=5):
            frames.append(frame)
            finished_at.append(len(probe.finished))
        return frames, finished_at

    frames, finished_at = asyncio.run(consume())
    events = parse_sse("".join(frames))
    assert len(frames) == len(events), "yield one event at a time"
    assert events[-1] == ("done", {"results": 19, "errors": 1, "orchestrator_tokens": 150}), (
        "done reports the counts and the orchestrator's context, which holds only the results"
    )
    assert ("error", {"session_id": "lead.sub07", "error": "ValueError: no tests for module 07"}) in events, (
        "a failed subagent is reported and the others carry on"
    )
    assert ("subagent_result", {"session_id": "lead.sub03", "result": "tests for module 03 are in tests/test_03.py"}) in events
    assert [data["session_id"] for _, data in events[:-1]] == probe.finished, "outcomes arrive in the order subagents finish"
    assert store.list_subkeys("lead") == [f"lead.sub{i:02d}" for i in range(1, 21)]
    assert context_of(store, "lead") == 150, "only results return to the orchestrator"
    assert finished_at[0] < 5, "send each outcome as soon as its subagent finishes"
    assert probe.peak <= 5, "at most five subagents run at once"
    assert probe.peak == 5, "run five subagents at a time"
    assert probe.finished[-1] == "lead.sub01", "a finished subagent frees its slot right away"

    store = SessionStore()
    probe = Probe(store, {f"module {i:02d}": 50 + 10 * i for i in range(1, 11)})

    async def stop_early() -> tuple[int, int, int]:
        stream = fan_out(store, "lead", [f"module {i:02d}" for i in range(1, 11)], probe)
        await stream.__anext__()
        await stream.__anext__()
        started = len(probe.started)
        await stream.aclose()
        active = probe.active
        for _ in range(20):
            await asyncio.sleep(0)
        return started, active, len(probe.started)

    started, active, started_later = asyncio.run(stop_early())
    assert active == 0, "closing the stream cancels the subagents still running"
    assert started_later == started, "no new subagents start after the stream is closed"


def build_tree(store: SessionStore, sessions: list[tuple]) -> None:
    for sid, parent, *stamps in sessions:
        if parent is not None:
            store.link_sub(parent, sid)
        for ts in stamps:
            store.append(sid, Turn("user", "work", ts))


@pytest.mark.skip("Part 5")
def test_subagent_tree() -> None:
    """Render the subagent tree, and expire whole subtrees that went idle."""
    store = SessionStore()
    build_tree(store, [
        ("lead", None, 90.0, 95.0, 100.0),
        ("lead/tests", "lead", 105.0, 110.0),
        ("lead/tests/unit", "lead/tests", 800.0),
        ("lead/docs", "lead", 120.0),
        ("lead/docs/draft", "lead/docs"),
        ("other", None, 100.0, 900.0),
        ("other/sub01", "other", 40.0, 45.0, 48.0, 50.0),
        ("other/sub01/sub01", "other/sub01", 60.0),
        ("solo", None, 10.0),
        ("nightly", None, 700.0),
        ("fresh", None, 990.0),
    ])
    assert render_tree(store, "lead") == (
        "lead  turns=3 subtree=7\n"
        "  lead/tests  turns=2 subtree=3\n"
        "    lead/tests/unit  turns=1 subtree=1\n"
        "  lead/docs  turns=1 subtree=1\n"
        "    lead/docs/draft  turns=0 subtree=0\n"
    ), "one indented line per session, children in the order they were linked"
    assert render_tree(store, "other/sub01") == "other/sub01  turns=4 subtree=5\n  other/sub01/sub01  turns=1 subtree=1\n"
    with pytest.raises(ValueError):
        render_tree(store, "nobody")

    assert prune_expired(store, now=1000.0, ttl_s=300.0) == [
        "lead/docs", "lead/docs/draft", "other/sub01", "other/sub01/sub01", "solo",
    ], "a session expires only when it and every session below it are idle"
    assert store.list_sessions() == ["fresh", "lead", "lead/tests", "lead/tests/unit", "nightly", "other"]
    assert store.list_subkeys("lead") == ["lead/tests"] and store.list_subkeys("other") == []

    deep = SessionStore()
    build_tree(deep, [(f"d{i}", f"d{i - 1}" if i else None, 0.0) for i in range(1200)])
    lines = render_tree(deep, "d0").split("\n")
    assert lines[0] == "d0  turns=1 subtree=1200", "deep trees render too"
    assert lines[-2] == "  " * 1199 + "d1199  turns=1 subtree=1" and lines[-1] == ""
    assert prune_expired(deep, now=1000.0, ttl_s=300.0) == sorted(f"d{i}" for i in range(1200)), "deep trees expire too"
    assert deep.list_sessions() == []

    shared = SessionStore()
    build_tree(shared, [("a", None, 0.0), ("b", None, 0.0), ("c", "a", 0.0)])
    shared.link_sub("b", "c")
    with pytest.raises(ValueError):
        render_tree(shared, "a")
    with pytest.raises(ValueError):
        prune_expired(shared, now=1000.0, ttl_s=300.0)
    assert shared.list_sessions() == ["a", "b", "c"], "a malformed tree is rejected before anything is deleted"

    loop = SessionStore()
    build_tree(loop, [("x", None, 0.0), ("y", "x", 0.0), ("z", None, 0.0)])
    loop.link_sub("y", "x")
    with pytest.raises(ValueError):
        prune_expired(loop, now=1000.0, ttl_s=300.0)
    assert loop.list_sessions() == ["x", "y", "z"]
