import asyncio
import json
import math
import random
import re
import time
from collections import Counter
from dataclasses import replace

import pytest
from rewoo.agent import ScriptedPlanner, ScriptedSolver, run_rewoo
from rewoo.dataset import Example, PlanDataset
from rewoo.nested import SubPlan, flatten
from rewoo.plan import MISSING, Evidence, Plan, Step
from rewoo.replan import Patch, plan_and_execute
from rewoo.stream import stream_plan
from rewoo.workers import ToolRegistry, run_workers

FACTS = {
    "capital of France": "Paris",
    "capital of Germany": "Berlin",
    "population of Paris": '2.1 million ("Paris proper")',
    "population of Berlin": "3.7 million",
    "river of Berlin": "Spree",
}


def number_in(text: str) -> float:
    """The first number in a piece of text, read the way a quick tool would."""
    match = re.search(r"\d+(?:\.\d+)?", text)
    if match is None:
        raise ValueError(f"no number in {text!r}")
    return float(match.group())


class World:
    """Fake tools over a fixed table of facts. Every call is recorded with what the tool received."""

    def __init__(self, facts: dict[str, str] = FACTS) -> None:
        self.facts = facts
        self.calls: list[tuple] = []
        self.tools = ToolRegistry()
        for name in ("search", "largest", "total", "round_million", "echo"):
            self.tools.register(name, getattr(self, name))

    def search(self, query: str, top_k: int = 1) -> str:
        self.calls.append(("search", query))
        if type(top_k) is not int:
            raise TypeError(f"top_k must be an int, got {top_k!r}")
        if query not in self.facts:
            raise LookupError(f"no result for {query!r}")
        return self.facts[query]

    def largest(self, items: list, title: str = "") -> str:
        self.calls.append(("largest", json.dumps(items)))
        return max(items, key=lambda item: number_in(item["population"]))["name"]

    def total(self, values: list) -> str:
        """Adds up the numbers it finds; a value without a number is left out."""
        self.calls.append(("total", tuple(values)))
        found = [number_in(value) for value in values if re.search(r"\d", value)]
        return f"{sum(found):.1f} million"

    def round_million(self, text: str) -> str:
        self.calls.append(("round_million", text))
        return f"{round(number_in(text))} million"

    def echo(self, text: str) -> str:
        self.calls.append(("echo", text))
        return text


def comparison_plan() -> Plan:
    """E3 compares two populations that E4 and E5, further down the list, look up."""
    return Plan(
        [
            Step("E1", "search", {"query": "capital of France"}),
            Step("E2", "search", {"query": "capital of Germany", "top_k": 1}),
            Step(
                "E3",
                "largest",
                {
                    "items": [{"name": "#E1", "population": "#E4"}, {"name": "#E2", "population": "#E5"}],
                    "title": "#E1 or #E2",
                },
            ),
            Step("E4", "search", {"query": "population of #E1"}),
            Step("E5", "search", {"query": "population of #E2"}),
        ]
    )


TEN_CITIES = ["Paris", "Berlin", "Madrid", "Rome", "Vienna", "Lisbon", "Athens", "Dublin", "Prague", "Oslo"]


@pytest.mark.skip("Part 1")
def test_run_plan() -> None:
    """Workers fill evidence in wherever a plan refers to it, contain failures, and keep up with long plans."""
    world = World()
    plan = comparison_plan()
    solver = ScriptedSolver("{E3} has more people: {E5} against {E4}.")
    run = run_rewoo("Which capital has more people?", ScriptedPlanner(plan), world.tools, solver)
    assert run.answer == 'Berlin has more people: 3.7 million against 2.1 million ("Paris proper").', (
        "the solver answers from the evidence of every step"
    )
    assert plan == comparison_plan(), "the plan itself is never rewritten"

    world = World()
    failing = Plan(
        [
            Step("E1", "search", {"query": "capital of Atlantis"}),
            Step("E2", "search", {"query": "population of #E1"}),
            Step("E3", "round_million", {"text": "#E2"}),
            Step("E4", "search", {"query": "capital of Germany"}),
            Step("E5", "serch", {"query": "population of #E4"}),
            Step("E6", "largest", {"items": [{"name": "#E4", "population": "#E5"}]}),
        ]
    )
    assert run_workers(failing, world.tools) == {
        "E1": Evidence("failed", "error: LookupError: no result for 'capital of Atlantis'"),
        "E2": Evidence("skipped", MISSING),
        "E3": Evidence("skipped", MISSING),
        "E4": Evidence("ok", "Berlin"),
        "E5": Evidence("failed", "error: unknown tool 'serch'"),
        "E6": Evidence("skipped", MISSING),
    }, "a step that needs a failed step is skipped, and so is everything after it"
    assert sorted(world.calls) == [("search", "capital of Atlantis"), ("search", "capital of Germany")], (
        "a skipped step never calls its tool"
    )

    world = World()
    dangling = Plan(
        [
            Step("E1", "search", {"query": "capital of France"}),
            Step("E2", "largest", {"items": [{"name": "#E1", "population": "#E9"}]}),
        ]
    )
    with pytest.raises(KeyError, match="E9"):
        run_workers(dangling, world.tools)
    assert world.calls == [], "a plan that cannot run calls no tool"
    with pytest.raises(ValueError):
        run_workers(Plan([Step("E1", "echo", {"text": "#E2"}), Step("E2", "echo", {"text": "#E1"})]), world.tools)
    with pytest.raises(ValueError):
        run_workers(Plan([Step("E1", "echo", {"text": "#E1 again"})]), world.tools)

    eleven = [Step(f"E{i}", "echo", {"text": city}) for i, city in enumerate(TEN_CITIES, 1)]
    eleven.append(Step("E11", "echo", {"text": "#E1, #E10 and #E2, then #E1 again"}))
    assert run_workers(Plan(eleven), World().tools)["E11"] == Evidence("ok", "Paris, Oslo and Berlin, then Paris again"), (
        "#E1 and #E10 are different steps"
    )

    n = 3000
    chain = Plan([Step(f"E{i}", "echo", {"text": f"#E{i - 1}" if i > 1 else "start"}) for i in range(n, 0, -1)])
    tools = World().tools
    start = time.perf_counter()
    evidence = run_workers(chain, tools)
    assert time.perf_counter() - start < 0.1, "run_workers should be fast on long plans"
    assert len(evidence) == n and evidence[f"E{n}"] == Evidence("ok", "start"), "every step of a long plan runs"


TRICKY = Example(
    question="Wie viele Menschen leben in der Hauptstadt Frankreichs?\u2028Und in Peking (北京)? 🌍",
    plan=Plan(
        [
            Step(
                "E1",
                "search",
                {"query": "capital of France", "top_k": 1, "min_score": 1.0, "exact": True, "lang": None},
            ),
            Step(
                "E2",
                "search",
                {"query": "population of #E1", "filters": {"year": 2024, "sources": ["census", "#E1 city hall"]}},
            ),
            Step(
                "E10",
                "largest",
                {"items": [{"name": "#E1", "population": "#E2"}, {"name": "北京", "population": "21.9 million"}]},
            ),
        ]
    ),
    answer="北京 hat mehr Einwohner: 21.9 Mio. gegen 2.1 Mio.",
    score=0.75,
)
PLAIN = Example(
    "What is the capital of France?",
    Plan([Step("E1", "search", {"query": "capital of France", "top_k": 1})]),
    "Paris",
    1,
)


@pytest.mark.skip("Part 2")
def test_plan_dataset(tmp_path) -> None:
    """Teacher plans for distillation round-trip exactly through an append-only JSONL file."""
    path = tmp_path / "plans.jsonl"
    data = PlanDataset(path)
    reader = PlanDataset(path)
    assert reader.examples() == [], "a new dataset is empty"
    assert data.append(TRICKY) is True and data.append(PLAIN) is True, "append returns True for a new example"
    assert len(reader.examples()) == 2, "a trainer sees every example while the teacher job is still writing"
    assert repr(reader.examples()) == repr([TRICKY, PLAIN]), "every field reads back exactly as it was appended"

    lines = path.read_text(encoding="utf-8").split("\n")
    assert len(lines) == 3 and lines[-1] == "", "one example per line, each line ends with a newline"
    first = json.loads(lines[0])
    assert (first["question"], first["answer"], first["score"]) == (TRICKY.question, TRICKY.answer, 0.75)
    assert first["steps"][1] == {
        "id": "E2",
        "tool": "search",
        "args": {"query": "population of #E1", "filters": {"year": 2024, "sources": ["census", "#E1 city hall"]}},
    }, "each line has the layout in the PlanDataset docstring"

    as_float = replace(PLAIN, plan=Plan([Step("E1", "search", {"query": "capital of France", "top_k": 1.0})]))
    as_bool = replace(PLAIN, plan=Plan([Step("E1", "search", {"query": "capital of France", "top_k": True})]))
    assert data.append(as_float) is True and data.append(as_bool) is True, "1, 1.0 and True make different plans"
    assert data.append(replace(PLAIN, answer="Paris, France", score=0.5)) is False, (
        "the same plan for the same question is stored once"
    )
    reworded = replace(PLAIN, question="Which city is the capital of France?")
    assert data.append(reworded) is True, "the same plan for another question is a new example"

    reopened = PlanDataset(path)
    assert len(reopened.examples()) == 5, "opening the file again keeps every example in it"
    assert reopened.append(PLAIN) is False, "a reopened dataset still knows what it holds"
    late = Example("And Germany?", Plan([Step("E1", "search", {"query": "capital of Germany"})]), "Berlin", 0.5)
    assert reopened.append(late) is True
    assert repr(PlanDataset(path).examples()) == repr([TRICKY, PLAIN, as_float, as_bool, reworded, late]), (
        "a reopened dataset appends after what is already there"
    )
    assert [ex.answer for ex in reopened.examples(min_score=0.75)] == [TRICKY.answer] + ["Paris"] * 4, (
        "examples(min_score) keeps the examples scored at least min_score"
    )

    before = path.read_bytes()
    spain = Example("What is the capital of Spain?", Plan([Step("E1", "search", {"query": "capital of Spain"})]), "Madrid", 1)
    for bad in (
        replace(spain, question=""),
        replace(spain, score=1.5),
        replace(spain, score=math.nan),
        replace(spain, score=True),
        replace(spain, plan=Plan([])),
        replace(spain, plan=Plan([Step("E1", "search", {"query": "Spain"}), Step("E1", "search", {"query": "Madrid"})])),
        replace(spain, plan=Plan([Step("E1", "largest", {"items": [{"name": "Madrid", "population": "#E2"}]})])),
    ):
        with pytest.raises(ValueError):
            reopened.append(bad)
    assert path.read_bytes() == before, "a rejected example writes nothing"
    assert reopened.append(replace(spain, score=0)) is True, "0 is a valid score, like 1"


PEOPLE = {
    "Paris": "2.1 million",
    "Berlin": "3.7 million",
    "Madrid": "3.3 million",
    "Rome": "no data",
    "Vienna": "2.0 million",
    "Lisbon": "0.5 million",
    "Athens": "0.6 million",
    "Dublin": "0.6 million",
}
EIGHT = list(PEOPLE)
CENSUS = {
    **{f"population of {city}": people for city, people in PEOPLE.items()},
    "population of Roma": "2.8 million",
    "capital of France": "Paris",
    "population of the capital of France": "2.1 million",
}


def eight_capitals() -> Plan:
    """Look up eight populations, add them up, round the total: ten steps, E1 to E10."""
    lookups = [Step(f"E{i}", "search", {"query": f"population of {city}"}) for i, city in enumerate(EIGHT, 1)]
    return Plan(
        lookups
        + [
            Step("E9", "total", {"values": [f"#E{i}" for i in range(1, 9)]}),
            Step("E10", "round_million", {"text": "#E9"}),
        ]
    )


def paris_plan() -> Plan:
    """The planner skipped E3."""
    return Plan(
        [
            Step("E1", "search", {"query": "capital of France"}),
            Step("E2", "search", {"query": "population of #E1 proper"}),
            Step("E4", "round_million", {"text": "#E2"}),
        ]
    )


class ScriptedReplanner:
    """Stands in for the replanner LLM: hands out its patches in order; None accepts the plan."""

    def __init__(self, *patches) -> None:
        self.patches = list(patches)
        self.shown: list[set[str]] = []
        self.accepted = False

    def review(self, question: str, plan: Plan, evidence: dict) -> Patch | None:
        assert not self.accepted, "once the replanner accepts the plan, it is not asked again"
        assert self.patches, "the replanner was asked for more patches than max_replans allows"
        assert {step.id for step in plan.steps} == set(evidence), (
            "the replanner reviews each live step with its evidence"
        )
        self.shown.append(set(evidence))
        patch = self.patches.pop(0)
        self.accepted = patch is None
        return patch


class Texts(dict):
    def __missing__(self, step_id: str) -> str:
        return f"<no {step_id}>"


class RecordingSolver:
    """Stands in for the solver LLM: fills in a template and remembers which evidence it was shown."""

    def __init__(self, template: str) -> None:
        self.template = template
        self.shown: set[str] = set()

    def solve(self, question: str, plan: Plan, evidence: dict) -> str:
        assert {step.id for step in plan.steps} == set(evidence), (
            "the solver answers from each live step with its evidence"
        )
        self.shown = set(evidence)
        return self.template.format_map(Texts({step_id: ev.text for step_id, ev in evidence.items()}))


ROMA = Patch(
    ["E4"],
    [
        Step("P1", "search", {"query": "population of Roma"}),
        Step("P2", "total", {"values": ["#E1", "#E2", "#E3", "#P1", "#E5", "#E6", "#E7", "#E8"]}),
        Step("P3", "round_million", {"text": "#P2"}),
    ],
)
METRO = Patch(
    ["E2"],
    [
        Step("P1", "search", {"query": "population of #E1 metro"}),
        Step("P2", "round_million", {"text": "#P1"}),
    ],
)
DIRECT = Patch(
    ["E1"],
    [
        Step("P1", "search", {"query": "population of the capital of France"}),
        Step("P2", "round_million", {"text": "#P1"}),
    ],
)


def replan(world: World, plan: Plan, *patches, template: str = "", max_replans: int = 2):
    """Run plan_and_execute with a scripted planner, replanner and solver, and hand them all back."""
    replanner, solver = ScriptedReplanner(*patches), RecordingSolver(template)
    run = plan_and_execute(
        "How many people live there?", ScriptedPlanner(plan), world.tools, replanner, solver, max_replans=max_replans
    )
    return run, replanner, solver


@pytest.mark.skip("Part 3")
def test_replan() -> None:
    """Plan-and-Execute: replan only what depends on unusable evidence, and keep everything else."""
    world = World(CENSUS)
    run, replanner, solver = replan(
        world, eight_capitals(), ROMA, None, template="About {E13} people live there.", max_replans=3
    )
    assert [step.id for step in run.plan.steps] == [f"E{i}" for i in range(1, 14)], (
        "patch steps are numbered after the highest step number in the plan"
    )
    assert run.plan.steps[10:] == [
        Step("E11", "search", {"query": "population of Roma"}),
        Step("E12", "total", {"values": ["#E1", "#E2", "#E3", "#E11", "#E5", "#E6", "#E7", "#E8"]}),
        Step("E13", "round_million", {"text": "#E12"}),
    ], "references between patch steps follow the new numbers; references to kept steps stay"
    assert run.dropped == {"E4", "E9", "E10"}, "a replaced step and every step downstream of it are dropped"
    assert run.evidence["E4"] == Evidence("ok", "no data") and len(run.evidence) == 13, (
        "the run keeps the evidence of every step it planned"
    )
    assert run.answer == "About 16 million people live there."
    live = {"E1", "E2", "E3", "E5", "E6", "E7", "E8", "E11", "E12", "E13"}
    assert solver.shown == live, "the solver never sees dropped evidence"
    assert replanner.shown == [{f"E{i}" for i in range(1, 11)}, live], "the replanner reviews the live steps"
    assert Counter(name for name, _ in world.calls) == {"search": 9, "total": 2, "round_million": 2}, (
        "kept steps never run again"
    )

    world = World(CENSUS)
    run, replanner, solver = replan(world, paris_plan(), METRO, DIRECT, template="About {E8} people.")
    assert [step.id for step in run.plan.steps] == ["E1", "E2", "E4", "E5", "E6", "E7", "E8"], (
        "a new id never takes the number of a step that already exists"
    )
    assert run.evidence["E5"] == Evidence("failed", "error: LookupError: no result for 'population of Paris metro'")
    assert run.dropped == {"E1", "E2", "E4", "E5", "E6"}, "dropping a step also drops later patch steps that used it"
    assert (solver.shown, run.answer) == ({"E7", "E8"}, "About 2 million people.")
    assert [name for name, _ in world.calls] == ["search", "search", "search", "search", "round_million"], (
        "every step that runs, runs once; a skipped step never runs"
    )
    assert replanner.shown == [{"E1", "E2", "E4"}, {"E1", "E5", "E6"}], (
        "the replanner also reviews failed and skipped steps"
    )

    run, _, _ = replan(World(CENSUS), paris_plan(), METRO, template="{E1}: {E5}, then {E6}", max_replans=1)
    assert run.answer == f"Paris: error: LookupError: no result for 'population of Paris metro', then {MISSING}", (
        "after max_replans patches the solver answers with the evidence there is"
    )
    run, _, _ = replan(World(CENSUS), paris_plan(), template="{E4}", max_replans=0)
    assert (run.dropped, run.answer) == (set(), MISSING), "max_replans=0 is plain ReWOO"
    with pytest.raises(ValueError):
        replan(World(CENSUS), paris_plan(), max_replans=-1)

    roma = Step("P1", "search", {"query": "population of Roma"})
    for patch, error, name in (
        (Patch(["E4"], [roma, Step("P2", "total", {"values": ["#E9", "#P1"]})]), ValueError, "E9"),
        (Patch(["E4"], [Step("P1", "search", {"query": "population of #E99"})]), KeyError, "E99"),
        (Patch(["E4"], [roma, Step("P2", "total", {"values": ["#E1", "#P3"]})]), KeyError, "P3"),
        (Patch(["E12"], []), KeyError, "E12"),
    ):
        world = World(CENSUS)
        with pytest.raises(error, match=name):
            replan(world, eight_capitals(), patch, None)
        assert len(world.calls) == 10, "a rejected patch runs nothing"


STREAMED = (
    "Plan: compare the two capitals, then check the numbers.\n"
    "#E1 = search[capital of France]\n"
    "#E5 = largest[#E1: #E3; #E2: #E4]\n"
    "#E7 = search[river of #E2]\n"
    "\n"
    "#E3 = search[population of #E1]\n"
    "#E6 = grep[[0-9.]+ million]\n"
    "#E4 = search[population of #E2]\n"
    "Plan: Germany's capital comes last.\n"
    "#E2 = search[capital of Germany]"
)
STREAMED_RECORDS = [
    ("E1", "search", "capital of France", "Paris"),
    ("E3", "search", "population of Paris", '2.1 million ("Paris proper")'),
    ("E6", "grep", "[0-9.]+ million", "Paris 2.1 million Berlin 3.7 million"),
    ("E2", "search", "capital of Germany", "Berlin"),
    ("E7", "search", "river of Berlin", "Spree"),
    ("E4", "search", "population of Berlin", "3.7 million"),
    ("E5", "largest", 'Paris: 2.1 million ("Paris proper"); Berlin: 3.7 million', "Berlin"),
]
RECORD = re.compile(r"#(E\d+) = (\w+)\[(.*)\] -> (.*)")


def text_tools(calls: list) -> ToolRegistry:
    """Tools for a streamed plan: each one takes a single string."""
    corpus = ["Paris 2.1 million", "Berlin 3.7 million", "Spree river"]

    def search(query: str) -> str:
        calls.append(("search", query))
        if query not in FACTS:
            raise LookupError(f"no result for {query!r}")
        return FACTS[query]

    def largest(pairs: str) -> str:
        calls.append(("largest", pairs))
        entries = [entry.split(": ") for entry in pairs.split("; ")]
        return max(entries, key=lambda entry: number_in(entry[1]))[0]

    def grep(pattern: str) -> str:
        calls.append(("grep", pattern))
        return "\n".join(line for line in corpus if re.search(pattern, line))

    tools = ToolRegistry()
    for fn in (search, largest, grep):
        tools.register(fn.__name__, fn)
    return tools


def run_stream(chunks: list[str], calls: list) -> list[tuple]:
    """Feed a plan to stream_plan chunk by chunk and parse the records it streams back."""

    async def planner():
        for chunk in chunks:
            yield chunk
            await asyncio.sleep(0)

    async def drain() -> list[str]:
        return [record async for record in stream_plan(planner(), text_tools(calls))]

    lines = "".join(asyncio.run(drain())).split("\n")
    assert lines[-1] == "", "every record ends with a newline"
    parsed = []
    for line in lines[:-1]:
        match = RECORD.fullmatch(line)
        assert match, f"one record per line, #E<k> = tool[input] -> evidence: {line!r}"
        parsed.append(match.groups())
    return parsed


@pytest.mark.skip("Part 4")
def test_stream_plan() -> None:
    """Run each step as soon as the planner has written its line and its evidence is ready."""
    rng = random.Random(7)
    chunkings = [[STREAMED], list(STREAMED)]
    for _ in range(40):
        cuts = sorted(rng.sample(range(1, len(STREAMED)), rng.randint(1, 15)))
        chunkings.append([STREAMED[a:b] for a, b in zip([0, *cuts], [*cuts, len(STREAMED)])])
    for chunks in chunkings:
        calls: list = []
        assert run_stream(chunks, calls) == STREAMED_RECORDS, (
            f"the same records however the plan is cut into chunks, e.g. {chunks[:4]}"
        )
        assert len(calls) == len(STREAMED_RECORDS), "every step runs once"

    cascade = (
        "#E3 = largest[#E1: #E2]\n"
        "#E2 = search[population of #E1]\n"
        "#E4 = grep[#E1|river]\n"
        "#E5 = search[#E4]\n"
        "#E1 = search[capital of Germany]\n"
    )
    assert [record[0] for record in run_stream([cascade], [])] == ["E1", "E2", "E3", "E4", "E5"], (
        "when several steps are ready, the one whose line came first runs first"
    )

    pulled: list[int] = []

    async def long_plan():
        for i in range(1, 51):
            pulled.append(i)
            yield f"#E{i} = search[capital of France]\n"
            await asyncio.sleep(0)

    async def first_record() -> str:
        records = stream_plan(long_plan(), text_tools([]))
        record = await records.__anext__()
        await records.aclose()
        return record

    assert asyncio.run(first_record()) == "#E1 = search[capital of France] -> Paris\n"
    assert len(pulled) <= 2, "a step runs as soon as its line is complete, while the planner is still writing"

    calls = []
    failing = (
        "#E1 = search[capital of Atlantis]\n"
        "#E2 = search[population of #E1]\n"
        "#E3 = serch[capital of Germany]\n"
        "#E4 = search[river of #E2]\n"
    )
    assert run_stream([failing], calls) == [
        ("E1", "search", "capital of Atlantis", "error: LookupError: no result for 'capital of Atlantis'"),
        ("E2", "search", "population of #E1", "skipped"),
        ("E3", "serch", "capital of Germany", "error: unknown tool 'serch'"),
        ("E4", "search", "river of #E2", "skipped"),
    ], "a failed step reports its error, and the steps that need it are skipped"
    assert calls == [("search", "capital of Atlantis")], "a skipped step never calls its tool"

    with pytest.raises(ValueError):
        run_stream(["#E1 = search[capital of France]\n#E1 = search[capital of Germany]\n"], [])
    with pytest.raises(ValueError):
        run_stream(["#E2 = search[#E1]\n#E2 = search[capital of Germany]\n#E1 = search[capital of France]\n"], [])
    with pytest.raises(KeyError, match="E9"):
        run_stream(["#E1 = search[capital of France]\n#E2 = search[population of #E9]\n"], [])
    with pytest.raises(ValueError):
        run_stream(["#E1 = search[capital of #E2]\n#E2 = search[capital of #E1]\n"], [])


def population_of(step_id: str, city: str) -> SubPlan:
    """A reusable sub-plan: look a city's population up and round it. Inside, #E1 is the city."""
    return SubPlan(
        step_id,
        [
            Step("E2", "search", {"query": "population of #E1"}),
            Step("E3", "round_million", {"text": "#E2"}),
        ],
        output="E3",
        imports={"E1": city},
    )


@pytest.mark.skip("Part 5")
def test_flatten() -> None:
    """Sub-plans with their own #E names expand into one flat plan the workers can run."""
    compare = Step(
        "E5", "largest", {"items": [{"name": "#E1", "population": "#E3"}, {"name": "#E2", "population": "#E4"}]}
    )
    nested = [
        Step("E1", "search", {"query": "capital of France"}),
        Step("E2", "search", {"query": "capital of Germany"}),
        population_of("E3", "E1"),
        population_of("E4", "E2"),
        compare,
    ]
    before = repr(nested)
    assert flatten(nested) == Plan(
        [
            Step("E1", "search", {"query": "capital of France"}),
            Step("E2", "search", {"query": "capital of Germany"}),
            Step("E6", "search", {"query": "population of #E1"}),
            Step("E3", "round_million", {"text": "#E6"}),
            Step("E7", "search", {"query": "population of #E2"}),
            Step("E4", "round_million", {"text": "#E7"}),
            compare,
        ]
    ), "inside a sub-plan, #E names are its own: imports, new ids, and its output in its place"
    assert repr(nested) == before, "flattening leaves the nested plan as it was"

    density = SubPlan(
        "E2",
        [
            Step("E8", "search", {"query": "area of #E9"}),
            population_of("E2", "E9"),
            Step("E4", "divide", {"values": ["#E2", "#E8"]}),
        ],
        output="E4",
        imports={"E9": "E1"},
    )
    wrapper = SubPlan("E4", [population_of("E1", "E7")], output="E1", imports={"E7": "E1"})
    assert flatten([Step("E1", "search", {"query": "capital of France"}), density, wrapper]) == Plan(
        [
            Step("E1", "search", {"query": "capital of France"}),
            Step("E5", "search", {"query": "area of #E1"}),
            Step("E7", "search", {"query": "population of #E1"}),
            Step("E6", "round_million", {"text": "#E7"}),
            Step("E2", "divide", {"values": ["#E6", "#E5"]}),
            Step("E8", "search", {"query": "population of #E1"}),
            Step("E4", "round_million", {"text": "#E8"}),
        ]
    ), "imports pass evidence down level by level, and an output can itself be a sub-plan"

    capital = Step("E1", "search", {"query": "capital of France"})
    with pytest.raises(KeyError, match="E8"):
        flatten([capital, population_of("E2", "E8")])
    with pytest.raises(KeyError, match="E1"):
        flatten([capital, SubPlan("E2", [Step("E2", "search", {"query": "population of #E1"})], output="E2")])
    with pytest.raises(KeyError, match="E1"):
        flatten([capital, SubPlan("E2", [population_of("E2", "E1")], output="E2")])
    with pytest.raises(ValueError):
        flatten([capital, SubPlan("E2", [], output="E1")])
    with pytest.raises(ValueError):
        flatten(
            [capital, SubPlan("E2", [Step("E1", "search", {"query": "x"})], output="E5", imports={"E5": "E1"})]
        )
    with pytest.raises(ValueError):
        flatten(
            [capital, SubPlan("E2", [Step("E1", "search", {"query": "x"})], output="E1", imports={"E1": "E1"})]
        )
    with pytest.raises(ValueError):
        flatten([capital, SubPlan("E2", [Step("E1", "search", {"query": "x"}), Step("E1", "echo", {"text": "y"})], output="E1")])
