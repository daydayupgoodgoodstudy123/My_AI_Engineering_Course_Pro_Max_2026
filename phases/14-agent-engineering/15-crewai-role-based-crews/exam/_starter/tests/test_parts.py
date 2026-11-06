import asyncio
import dbm
import json
import random
import re
import time

import pytest
from crewflow.crew import Agent, SequentialCrew, Task
from crewflow.entities import EntityMemory
from crewflow.events import AsyncFlow, logfmt
from crewflow.flow import Flow
from crewflow.hierarchy import HierarchicalCrew, ManagerCall, Round, Specialist, paragraphs
from crewflow.llm import KeyedLLM, ScriptedLLM
from crewflow.memory import Memory
from crewflow.rundiff import RunDiff, TraceNode, diff_runs


def agent(role: str, llm) -> Agent:
    return Agent(role=role, goal=f"do the {role}'s part", backstory="terse. cites primaries.", fn=llm)


def task(name: str, who: Agent, context=(), persistent: bool = False) -> Task:
    return Task(name, f"{name} for the brief", "plain text", who, list(context), persistent)


SOURCES = "3 sources on agent memory: MemGPT, Mem0, Letta"
DRAFT = "Agents forget everything between runs. Memory stores fix that."
BRIEF = {"title": "Agent memory", "summary": "Pick a store per fact.", "sections": ["short-term", "long-term"]}
SOURCES_2 = "3 sources on vector databases: FAISS, pgvector, Chroma"
DRAFT_2 = "Vector databases index embeddings for similarity search."
BRIEF_2 = {"title": "Vector databases", "summary": "Index once, query often.", "sections": ["indexes"]}
OUTLINE = "Outline: 1. why agents forget 2. memory stores 3. picking a store"
NOTES = "Notes per section: runs start cold; MemGPT, Mem0 and Letta; one store per fact"


@pytest.mark.skip("Part 1")
def test_crew_and_flow() -> None:
    """Tasks read their declared context, only persistent tasks are remembered, and every listener runs."""
    researcher = ScriptedLLM(SOURCES, SOURCES_2)
    writer = ScriptedLLM(DRAFT, DRAFT_2)
    editor = ScriptedLLM(BRIEF, BRIEF_2)
    people = [agent("researcher", researcher), agent("writer", writer), agent("editor", editor)]
    research = task("research", people[0], persistent=True)
    draft = task("draft", people[1])
    edit = task("edit", people[2], context=[research, draft])
    memory = Memory()
    crew = SequentialCrew(people, [research, draft, edit], memory=memory)

    assert crew.kickoff({"topic": "agent memory"}) == {"research": SOURCES, "draft": DRAFT, "edit": BRIEF}, (
        "kickoff returns every task's output by task name"
    )
    assert researcher.inputs == ["agent memory"], "the first task reads the topic"
    assert writer.inputs == [SOURCES], "a task without context reads the previous task's output"
    assert editor.inputs == [SOURCES + "\n\n" + DRAFT], "context joins the listed tasks' outputs, in order"
    assert memory.short_term == [("researcher", SOURCES), ("writer", DRAFT), ("editor", BRIEF)], (
        "short-term memory holds every task's output, in order"
    )
    recalled = memory.recall_long_term("sources on agent memory", k=5)
    assert [(role, text) for role, text, _ in recalled] == [("researcher", SOURCES)], (
        "only persistent tasks write long-term memory"
    )

    crew.kickoff({"topic": "vector databases"})
    assert memory.short_term == [("researcher", SOURCES_2), ("writer", DRAFT_2), ("editor", BRIEF_2)], (
        "short-term memory holds this run only"
    )
    recalled = memory.recall_long_term("which vector databases", k=5)
    assert [text for _, text, _ in recalled] == [SOURCES_2, SOURCES], "long-term memory keeps every kickoff"

    note_taker, drafter = ScriptedLLM(NOTES), KeyedLLM({NOTES + "\n\n" + OUTLINE: DRAFT})
    outline = task("outline", agent("planner", ScriptedLLM(OUTLINE)))
    research = task("research", agent("researcher", note_taker))
    draft = task("draft", agent("writer", drafter), context=[research, outline])
    assert SequentialCrew([], [outline, research, draft]).kickoff({"topic": "agent memory"}) == {
        "outline": OUTLINE,
        "research": NOTES,
        "draft": DRAFT,
    }, "kickoff returns every task's output by task name"
    assert note_taker.inputs == [OUTLINE], "a task without context reads the previous task's output"
    assert drafter.inputs == [NOTES + "\n\n" + OUTLINE], "context comes in the order the task lists it"

    checker, fixer = ScriptedLLM(""), KeyedLLM({"": "no corrections"})
    research = task("research", agent("researcher", ScriptedLLM(SOURCES)))
    fact_check = task("fact_check", agent("checker", checker), context=[research])
    draft = task("draft", agent("writer", ScriptedLLM(DRAFT)), context=[research])
    corrections = task("corrections", agent("fixer", fixer), context=[fact_check])
    SequentialCrew([], [research, fact_check, draft, corrections]).kickoff({"topic": "agent memory"})
    assert fixer.inputs == [""], "an empty upstream output is still the task's context"

    first = ScriptedLLM(SOURCES)
    research = task("research", agent("researcher", first))
    outline = task("outline", agent("writer", ScriptedLLM("outline")))
    draft = task("draft", agent("writer", ScriptedLLM(DRAFT)), context=[outline])
    with pytest.raises(ValueError, match="outline"):
        SequentialCrew([], [research, draft, outline]).kickoff({"topic": "agent memory"})
    assert first.inputs == [], "a crew that cannot run fails before any agent runs"
    legal = task("legal_review", agent("lawyer", ScriptedLLM("ok")))
    sign_off = task("sign_off", agent("editor", ScriptedLLM("ok")), context=[legal])
    with pytest.raises(ValueError, match="legal_review"):
        SequentialCrew([], [research, sign_off]).kickoff({"topic": "agent memory"})
    assert first.inputs == [], "a crew that cannot run fails before any agent runs"

    flow = Flow()

    @flow.start
    def gather(topic: str):
        return "researched", f"3 sources on {topic}"

    @flow.listen("researched")
    def write(sources: str):
        return "drafted", "draft from " + sources

    @flow.listen("researched")
    def archive_sources(sources: str):
        return None

    @flow.listen("drafted")
    def tighten(text: str):
        return "edited", "brief: " + text

    assert flow.kickoff("agent memory") == [
        ("gather", "researched", "3 sources on agent memory"),
        ("write", "drafted", "draft from 3 sources on agent memory"),
        ("archive_sources", None, None),
        ("tighten", "edited", "brief: draft from 3 sources on agent memory"),
    ], "every listener of a topic runs, in registration order"

    rng = random.Random(15)
    vocabulary = [f"term{i}" for i in range(300)]
    notes = Memory()
    for _ in range(60):  # long research notes, about 3,000 words each
        notes.write_long_term("researcher", " ".join(rng.choices(vocabulary, k=3000)))
    queries = [" ".join(rng.choices(vocabulary, k=4)) for _ in range(30)]
    notes.recall_long_term(queries[0])  # the first recall may do one-time work
    start = time.perf_counter()
    for query in queries:
        notes.recall_long_term(query, k=3)
    assert time.perf_counter() - start < 0.1, "recall_long_term should stay fast as long-term memory grows"


ACME_LABS = {"plan": "enterprise", "seats": "300", "renewal": "2026-12-01"}
MULLER = {"contact": "Jürgen Müller", "ship_to": "Halle 4\nTor B\n", "po": "PO-77\r\nref 3"}
NEKO = {"tone": "  formal, no emoji  ", "note": 'says "urgent" = today', "path": "C:\\briefs\\neko"}


@pytest.mark.skip("Part 2")
def test_entity_memory(tmp_path) -> None:
    """Facts about an entity survive across kickoffs exactly, found by the exact entity name."""
    path = str(tmp_path / "entities")
    store = EntityMemory(path)  # first kickoff
    store.remember("Acme Labs", {"plan": "enterprise", "seats": "250"})
    store.remember("株式会社ネコ", NEKO)
    store.remember("Acme", {"plan": "free"})
    store.remember("Müller & Söhne GmbH", MULLER)
    store.remember("Acme Labs", {"seats": "300", "renewal": "2026-12-01"})
    assert store.recall("Acme Labs") == ACME_LABS, "remembering a fact keeps the entity's other facts"
    store.close()

    store = EntityMemory(path)  # second kickoff
    names = ["Acme", "Acme Labs", "Müller & Söhne GmbH", "株式会社ネコ"]
    assert store.entities() == names, "a reopened store lists every entity by its exact name, sorted"
    assert store.recall("Müller & Söhne GmbH") == MULLER, "facts come back exactly"
    assert store.recall("株式会社ネコ") == NEKO, "facts come back exactly"
    assert store.recall("Acme") == {"plan": "free"}, "facts are found by the exact entity name"
    assert store.recall("Acme Labs") == ACME_LABS
    assert store.recall("Globex") == {}, "an unknown entity has no facts"
    assert store.recall("acme") == store.recall("Acme ") == {}, "facts are found by the exact entity name"
    facts = store.recall("Acme Labs")
    facts["plan"] = "free"
    assert store.recall("Acme Labs")["plan"] == "enterprise", "recall hands out a copy"
    with pytest.raises(ValueError):
        store.remember("", {"plan": "free"})
    store.remember("Acme", {"plan": "team"})
    store.close()

    def as_json(value: bytes):
        try:
            return json.loads(value)
        except ValueError:
            return None

    with dbm.open(path, "r") as raw:
        keys = sorted(key.decode("utf-8", "replace") for key in raw.keys())
        assert keys == names, "one dbm key per entity: its name in UTF-8"
        assert as_json(raw["Acme".encode("utf-8")]) == {"plan": "team"}, (
            "each value is the entity's facts as one JSON object"
        )
        assert as_json(raw["Müller & Söhne GmbH".encode("utf-8")]) == MULLER, (
            "each value is the entity's facts as one JSON object"
        )


SOURCES_TEXT = "MemGPT pages memory.\nMem0 extracts facts.\nLetta keeps blocks."
TWO_PARAGRAPHS = "Agents forget between runs.\n\nMemory stores fix that."
THREE_PARAGRAPHS = "Agents forget between runs.\nEvery run starts cold.\n\nMemory stores fix that.\n\nPick a store per fact."


class Manager:
    """A rule-based stand-in for the manager LLM: the first role in order without output, then done."""

    def __init__(self, order=("researcher", "writer", "editor"), answers=()) -> None:
        self.order = order
        self.answers = list(answers)
        self.views = []

    def __call__(self, view):
        self.views.append(view)
        assert len(self.views) <= 20, "the manager was asked more than 20 times"
        if self.answers:
            return self.answers.pop(0)
        produced = {role for role, _ in view.outputs}
        return next((role for role in self.order if role not in produced), "done")


def brief_crew(manager: Manager, drafts: list, max_steps: int = 10):
    researcher = ScriptedLLM(SOURCES_TEXT)
    writer = ScriptedLLM(*drafts)
    editor = ScriptedLLM("Final brief.")
    crew = HierarchicalCrew(
        agent("manager", manager),
        [
            Specialist(agent("researcher", researcher), "find 3 credible sources"),
            Specialist(agent("writer", writer), "draft the brief"),
            Specialist(agent("editor", editor), "tighten the draft", min_paragraphs=3),
        ],
        max_steps=max_steps,
    )
    return crew, writer, editor


@pytest.mark.skip("Part 3")
def test_hierarchical_routing() -> None:
    """The manager routes every round; the crew refuses an editor pick until the draft has three paragraphs."""
    assert [
        paragraphs(text)
        for text in (
            "",
            " \n\t\n",
            "One paragraph,\nwrapped over two lines.",
            THREE_PARAGRAPHS,
            "\n\nFirst.\n\n\n\nSecond.\n\n",
            "First.\n   \nSecond.\n\t\nThird.",
            "First.\r\n\r\nSecond.\r\n\r\nThird.\r\n",
        )
    ] == [0, 0, 1, 3, 2, 3, 3], "paragraphs are separated by blank lines"

    manager = Manager()
    crew, writer, editor = brief_crew(manager, [TWO_PARAGRAPHS, THREE_PARAGRAPHS])
    run = crew.kickoff("agent memory")
    assert run.rounds == [
        Round("researcher", "researcher", None),
        Round("writer", "writer", None),
        Round("editor", "writer", "editor needs 3 paragraphs from writer, got 2"),
        Round("editor", "editor", None),
        Round("done", None, None),
    ], "a refused editor pick sends the writer back to its draft"
    assert writer.inputs == [SOURCES_TEXT, SOURCES_TEXT], "the writer redoes its draft from the researcher's output"
    assert editor.inputs == [THREE_PARAGRAPHS], "the editor reads the accepted draft"
    assert (run.stop, run.outputs) == (
        "done",
        {"researcher": SOURCES_TEXT, "writer": THREE_PARAGRAPHS, "editor": "Final brief."},
    ), "the run ends when the manager says done, with every specialist's latest output"
    assert (len(run.manager_calls), run.specialist_calls) == (5, 4), (
        "one manager call per round, plus the one that says done"
    )
    assert [len(view.outputs) for view in manager.views] == [0, 1, 2, 3, 4], (
        "each manager call sees the outputs up to that round"
    )
    assert list(manager.views[4].outputs) == [
        ("researcher", SOURCES_TEXT),
        ("writer", TWO_PARAGRAPHS),
        ("writer", THREE_PARAGRAPHS),
        ("editor", "Final brief."),
    ], "the manager is sent every specialist call's output, oldest first, rejected drafts included"
    assert manager.views[3].refusals == ("editor needs 3 paragraphs from writer, got 2",), (
        "the manager is told why a pick was refused"
    )
    assert manager.views[0].tasks == (
        "researcher: find 3 credible sources",
        "writer: draft the brief",
        "editor: tighten the draft",
    ), "the manager is sent the whole task list"
    s, d2, d3 = len(SOURCES_TEXT), len(TWO_PARAGRAPHS), len(THREE_PARAGRAPHS)
    assert run.manager_calls == [
        ManagerCall(3, 0),
        ManagerCall(3, s),
        ManagerCall(3, s + d2),
        ManagerCall(3, s + d2 + d3),
        ManagerCall(3, s + d2 + d3 + len("Final brief.")),
    ], "every manager call carries the task list and every earlier output"

    crew, _, _ = brief_crew(Manager(), [THREE_PARAGRAPHS], max_steps=4)
    assert crew.kickoff("agent memory").stop == "done", "max_steps counts rounds, the one that says done included"
    crew, _, _ = brief_crew(Manager(), [THREE_PARAGRAPHS], max_steps=3)
    run = crew.kickoff("agent memory")
    assert (run.stop, len(run.rounds), run.outputs["editor"]) == ("max_steps", 3, "Final brief."), (
        "a run cut short by max_steps says so"
    )

    crew, writer, _ = brief_crew(Manager(), [TWO_PARAGRAPHS] * 6, max_steps=6)
    run = crew.kickoff("agent memory")
    assert (run.stop, len(run.manager_calls), run.specialist_calls) == ("max_steps", 6, 6), (
        "a refused round still counts against max_steps"
    )
    assert [r.ran for r in run.rounds] == ["researcher"] + ["writer"] * 5, "every refused round sends the writer back"

    manager = Manager(order=("editor",))
    crew, writer, editor = brief_crew(manager, [THREE_PARAGRAPHS])
    run = crew.kickoff("agent memory")
    assert run.rounds == [
        Round("editor", "researcher", "editor needs writer's output first"),
        Round("editor", "writer", "editor needs writer's output first"),
        Round("editor", "editor", None),
        Round("done", None, None),
    ], "a pick that is not ready runs the nearest upstream specialist that is"
    assert manager.views[-1].refusals == ("editor needs writer's output first",) * 2, (
        "the manager is told why each earlier pick was refused"
    )

    analyst = ScriptedLLM("Churn is up.", "Churn is up.\n\nMostly on the free plan.")
    reviewer = ScriptedLLM("Approved.")
    crew = HierarchicalCrew(
        agent("lead", Manager(order=("analyst", "reviewer"))),
        [
            Specialist(agent("analyst", analyst), "explain the churn numbers"),
            Specialist(agent("reviewer", reviewer), "approve the analysis", min_paragraphs=2),
        ],
    )
    run = crew.kickoff("Q3 churn")
    assert [r.refused for r in run.rounds] == [None, "reviewer needs 2 paragraphs from analyst, got 1", None, None], (
        "each specialist's own min_paragraphs gates its input"
    )
    assert reviewer.inputs == ["Churn is up.\n\nMostly on the free plan."]

    crew, _, _ = brief_crew(Manager(answers=["researcher", "designer"]), [THREE_PARAGRAPHS])
    with pytest.raises(ValueError, match="designer"):
        crew.kickoff("agent memory")


LOGFMT_PAIR = re.compile(r'([a-z_]+)=("(?:[^"\\\x00-\x1f\x7f]|\\["\\nrt])*"|[^ "=\\\x00-\x1f\x7f]+)')
UNESCAPE = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}


def parse_logfmt(line: str) -> list[tuple[str, str]]:
    """Parse one logfmt line strictly: key=value pairs one space apart, values bare or double-quoted."""
    assert line.endswith("\n") and line.count("\n") == 1, f"one line per step, ending in a newline: {line!r}"
    body, pairs, pos = line[:-1], [], 0
    while True:
        match = LOGFMT_PAIR.match(body, pos)
        assert match, f"not a logfmt line: {line!r}"
        key, raw = match.groups()
        if raw.startswith('"'):
            raw = re.sub(r"\\(.)", lambda m: UNESCAPE[m[1]], raw[1:-1])
        pairs.append((key, raw))
        pos = match.end()
        if pos == len(body):
            return pairs
        assert body[pos] == " " and body[pos + 1 : pos + 2] not in ("", " "), f"not a logfmt line: {line!r}"
        pos += 1


def fields(line: str) -> list[tuple[str, str]]:
    """The pairs of one line, with the duration checked and blanked out."""
    pairs = parse_logfmt(line)
    for i, (key, value) in enumerate(pairs):
        if key == "duration_ms":
            assert value.isdigit(), f"duration_ms is whole milliseconds: {line!r}"
            pairs[i] = (key, "*")
    return pairs


async def next_line(agen, timeout: float = 1.0):
    try:
        return await asyncio.wait_for(agen.__anext__(), timeout)
    except StopAsyncIteration:
        return "ended"
    except asyncio.TimeoutError:
        return None


@pytest.mark.skip("Part 4")
def test_flow_event_log() -> None:
    """Listeners of a topic run concurrently, and every step is logged in logfmt the moment it completes."""
    assert logfmt([("step", "draft"), ("out", 'a "b" = c\\d')]) == 'step=draft out="a \\"b\\" = c\\\\d"', (
        "a value with spaces, quotes, equals signs or backslashes is quoted and escaped"
    )
    assert logfmt([("a", "x=1"), ("b", 'say"hi"'), ("c", "")]) == 'a="x=1" b="say\\"hi\\"" c=""', (
        "a value is quoted when it is empty or holds an equals sign or a quote, even without a space"
    )

    async def gated() -> tuple[list, object]:
        gates = {name: asyncio.Event() for name in ("research", "cite_check", "file_citations", "draft", "edit")}
        flow = AsyncFlow()

        @flow.start
        async def research(topic):
            await gates["research"].wait()
            return "researched", f"3 sources on {topic}"

        @flow.listen("researched")
        async def draft(sources):
            await gates["draft"].wait()
            return "drafted", 'draft: "agents" = loops + tools'

        @flow.listen("researched")
        async def cite_check(sources):
            await gates["cite_check"].wait()
            return "checked", ""

        @flow.listen("checked")
        async def file_citations(notes):
            await gates["file_citations"].wait()
            return None

        @flow.listen("drafted")
        async def edit(text):
            await gates["edit"].wait()
            return "edited", "Final brief – für alle\r\nTabs\there, saved to C:\\briefs\\17"

        agen = flow.run("agent memory")
        lines = []
        for name in gates:  # each step is released only after the previous line came out
            gates[name].set()
            line = await next_line(agen)
            lines.append(line)
            if line in (None, "ended"):
                return lines, None
        return lines, await next_line(agen)

    lines, after = asyncio.run(gated())
    assert None not in lines, "every step is logged the moment it completes, while other steps still run"
    assert "ended" not in lines, "a step that returns None ends only its own branch"
    assert [fields(line) for line in lines] == [
        [("step", "research"), ("topic", "researched"), ("duration_ms", "*"), ("out", "3 sources on agent memory")],
        [("step", "cite_check"), ("topic", "checked"), ("duration_ms", "*"), ("out", "")],
        [("step", "file_citations"), ("duration_ms", "*")],
        [("step", "draft"), ("topic", "drafted"), ("duration_ms", "*"), ("out", 'draft: "agents" = loops + tools')],
        [("step", "edit"), ("topic", "edited"), ("duration_ms", "*"), ("out", "Final brief – für alle\r\nTabs\there, saved to C:\\briefs\\17")],
    ], "one line per step: step, topic, duration_ms and out, or just step and duration_ms when the branch ends"
    assert after == "ended", "the run ends once no step is running"

    async def timed() -> list:
        flow = AsyncFlow()

        @flow.start
        async def slow(topic):
            await asyncio.sleep(0.06)
            return "slowed", topic

        @flow.listen("slowed")
        async def quick(topic):
            return None

        return [line async for line in flow.run("agent memory")]

    durations = [int(dict(parse_logfmt(line))["duration_ms"]) for line in asyncio.run(timed())]
    assert len(durations) == 2 and durations[0] >= 50 > durations[1], "duration_ms is each step's own run time"

    async def failing() -> tuple[list, object, list]:
        cancelled = []
        flow = AsyncFlow()

        @flow.start
        async def research(topic):
            return "researched", "3 sources"

        @flow.listen("researched")
        async def draft(sources):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append("draft")
                raise

        @flow.listen("researched")
        async def fact_check(sources):
            raise RuntimeError("search API is down")

        agen = flow.run("agent memory")
        lines = []
        try:
            while True:
                line = await next_line(agen)
                if line in (None, "ended"):
                    return lines, line, list(cancelled)
                lines.append(line)
        except RuntimeError as exc:
            await asyncio.sleep(0)
            return lines, exc, list(cancelled)

    lines, error, cancelled = asyncio.run(failing())
    assert isinstance(error, RuntimeError) and str(error) == "search API is down", "a step that raises fails the run"
    assert [fields(line) for line in lines] == [
        [("step", "research"), ("topic", "researched"), ("duration_ms", "*"), ("out", "3 sources")],
        [("step", "fact_check"), ("duration_ms", "*"), ("error", "RuntimeError: search API is down")],
    ], "a failing step is logged before the run fails"
    assert cancelled == ["draft"], "the steps still running are cancelled when one fails"


def node(name: str, output=None, *children: TraceNode) -> TraceNode:
    return TraceNode(name, output, tuple(children))


def crew_run(*tasks: TraceNode) -> TraceNode:
    return node("crew", None, *tasks)


GOOD_RUN = [
    node("intake", "topic: agent memory"),
    node(
        "research",
        "researched",
        crew_run(
            node("research", SOURCES),
            node("fact_check", None, crew_run(node("verify", "3 of 3 claims hold"))),
            node("draft", "Agents forget. Memory fixes that."),
        ),
    ),
    node("review", "2 notes"),
    node("revise", "revised", crew_run(node("draft", "Agents forget between runs."))),
    node("review", ""),
    node("publish", "brief-17"),
]
BAD_RUN = [
    node("intake", "topic: agent memory"),
    node(
        "research",
        "researched",
        crew_run(
            node("research", SOURCES),
            node("fact_check", None, crew_run(node("verify", "2 of 3 claims hold"))),
            node("cite", "added 2 citations", crew_run(node("lookup", "doi:10.1/xyz"))),
            node("draft", "Agents never forget."),
        ),
    ),
    node("review", "5 notes"),
    node("revise", "revised twice", crew_run(node("draft", "Agents rarely forget."))),
    node("review", "3 notes"),
    node("revise", "revised", crew_run(node("draft", "Agents forget between runs."))),
    node("review", ""),
]


@pytest.mark.skip("Part 5")
def test_run_diff() -> None:
    """Two runs' trace trees are aligned by step name and occurrence, and every difference is reported once."""
    assert diff_runs(GOOD_RUN, GOOD_RUN) == RunDiff(None, [], [], []), "identical runs have no differences"
    assert diff_runs(GOOD_RUN, BAD_RUN) == RunDiff(
        first="research[0]/crew[0]/fact_check[0]/crew[0]/verify[0]",
        missing=["publish[0]"],
        extra=["research[0]/crew[0]/cite[0]", "revise[1]", "review[2]"],
        changed=[
            "research[0]/crew[0]/fact_check[0]/crew[0]/verify[0]",
            "research[0]/crew[0]/draft[0]",
            "review[0]",
            "revise[0]",
            "revise[0]/crew[0]/draft[0]",
            "review[1]",
        ],
    ), "steps are matched by name and occurrence, depth first, and a one-sided subtree is reported once"
    research_tasks = GOOD_RUN[1].children[0].children
    cited = [
        GOOD_RUN[0],
        node("research", "researched", crew_run(*research_tasks, node("cite", "added 2 citations"))),
        node("review", "1 note"),
        *GOOD_RUN[3:],
    ]
    assert diff_runs(GOOD_RUN, cited) == RunDiff(
        "research[0]/crew[0]/cite[0]", [], ["research[0]/crew[0]/cite[0]"], ["review[0]"]
    ), "first is the earliest difference of any kind, in reading order"
    skipped = [GOOD_RUN[0], node("review", "no sources to review"), *GOOD_RUN[3:]]
    assert diff_runs(GOOD_RUN, skipped) == RunDiff("research[0]", ["research[0]"], [], ["review[0]"]), (
        "first is the earliest difference of any kind, in reading order"
    )
    retried = [GOOD_RUN[0], node("intake", "topic: agent memory, retried"), *GOOD_RUN[1:]]
    assert diff_runs(GOOD_RUN, retried) == RunDiff("intake[1]", [], ["intake[1]"], []), (
        "a repeated step is extra, not a shift of everything after it"
    )
    assert diff_runs(GOOD_RUN[:2], []) == RunDiff("intake[0]", ["intake[0]", "research[0]"], [], []), (
        "a run that stopped at once is missing every step"
    )
    triaged = [GOOD_RUN[0], node("triage", "routed to research"), GOOD_RUN[1], node("review", "1 note"), *GOOD_RUN[3:]]
    assert diff_runs(GOOD_RUN, triaged) == RunDiff("review[0]", [], ["triage[0]"], ["review[0]"]), (
        "a node only the bad run has comes after the good run's nodes at its level"
    )
    assert diff_runs([node("cite_check", "")], [node("cite_check")]) == RunDiff(
        "cite_check[0]", [], [], ["cite_check[0]"]
    ), "an empty output is still an output: '' and None differ"
