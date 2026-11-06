import asyncio
import configparser
import csv
import io
import json
import random
import time

import pytest
from htnplan.domain import Method, Operator
from htnplan.ensemble import stream_generations
from htnplan.evolve import evolve
from htnplan.library import Entry, MethodLibrary
from htnplan.llm import ScriptedLLM
from htnplan.planner import HTNPlanner
from htnplan.tree import Node, check, leaves


def op(name: str, pre=(), add=(), remove=()) -> Operator:
    return Operator(name, tuple(pre), tuple(add), tuple(remove))


OPERATORS = {
    o.name: o
    for o in (
        op("login", add=["logged_in"]),
        op("open_editor", ["logged_in"], ["editor_open"]),
        op("write_tests", ["editor_open"], ["tests_written"]),
        op("run_tests", ["tests_written"], ["tests_passing"]),
        op("open_pr", ["tests_passing"], ["pr_open"]),
        op("request_review", ["pr_open", "reviewer_online"], ["approved"]),
        op("admin_approve", ["pr_open", "admin"], ["approved"]),
        op("merge_pr", ["pr_open", "approved"], ["merged"], ["pr_open", "approved"]),
        op("build", ["merged"], ["artifact_built"]),
        op("push_canary", ["artifact_built", "canary_cluster"], ["canary_live"]),
        op("watch_canary", ["canary_live", "metrics_on"], ["canary_healthy"]),
        op("promote", ["canary_healthy"], ["deployed"], ["canary_live"]),
        op("push_prod", ["artifact_built", "logged_in"], ["deployed"]),
    )
}


def by_task(*methods: Method) -> dict[str, list[Method]]:
    grouped: dict[str, list[Method]] = {}
    for method in methods:
        grouped.setdefault(method.task, []).append(method)
    return grouped


METHODS = by_task(
    Method("reuse_session", "ensure_login", ("logged_in",), ()),
    Method("fresh_login", "ensure_login", (), ("login",)),
    Method(
        "ship_change_m1",
        "ship_change",
        (),
        ("ensure_login", "open_editor", "write_tests", "run_tests", "open_pr"),
    ),
    Method("merge_reviewed", "merge", ("pr_open",), ("request_review", "merge_pr")),
    Method(
        "deploy_canary",
        "deploy",
        ("artifact_built", "canary_cluster"),
        ("push_canary", "watch_canary", "promote"),
    ),
    Method("deploy_direct", "deploy", ("artifact_built",), ("ensure_login", "push_prod")),
    Method("release_m1", "release", (), ("ship_change", "merge", "build", "deploy")),
    Method("redeploy_existing", "redeploy", (), ("deploy",)),
    Method("redeploy_from_main", "redeploy", ("merged",), ("build", "deploy")),
)
SHIP = ["open_editor", "write_tests", "run_tests", "open_pr"]


@pytest.mark.skip("Part 1")
def test_plan_and_learn() -> None:
    """The planner backtracks over methods, learns only LLM decompositions that work, and stays fast."""
    planner = HTNPlanner(OPERATORS, METHODS, ScriptedLLM({"merge": [("admin_approve", "merge_pr")]}))
    state = {"logged_in", "reviewer_online", "canary_cluster"}
    assert planner.plan("release", state) == [*SHIP, "request_review", "merge_pr", "build", "push_prod"], (
        "when a method fails further down, try the next one"
    )
    assert state == {"logged_in", "reviewer_online", "canary_cluster"}, "planning leaves the caller's state alone"
    assert planner.plan("release", state | {"metrics_on"}) == [
        *SHIP,
        "request_review",
        "merge_pr",
        "build",
        "push_canary",
        "watch_canary",
        "promote",
    ], "methods are tried in library order"
    assert planner.plan("redeploy", {"logged_in", "merged"}) == ["build", "push_prod"], (
        "a task that failed from one state can still work from another"
    )
    assert planner.llm.calls == ["deploy"], "ask the LLM only where the library has nothing that works"
    assert planner.plan("merge", {"pr_open", "admin"}) == ["admin_approve", "merge_pr"], (
        "when no library method works, ask the LLM"
    )
    assert planner.plan("merge", {"pr_open", "admin", "reviewer_online"}) == ["request_review", "merge_pr"], (
        "library methods come before learned ones"
    )

    llm = ScriptedLLM(
        {"hotfix": [("open_editor", "push_to_main"), ("open_pr",), tuple(SHIP), ("open_pr",), ("ship_change",)]}
    )
    planner = HTNPlanner(OPERATORS, METHODS, llm)
    assert planner.plan("hotfix", {"logged_in"}) is None and llm.calls == ["hotfix"], (
        "a reply that names something outside the schema is rejected as a whole, not planned"
    )
    assert planner.plan("hotfix", {"logged_in"}) is None
    assert planner.cached_methods == {}, "a decomposition that does not expand is never learned"
    assert planner.plan("hotfix", {"logged_in"}) == SHIP, "a new request asks the LLM again"
    assert planner.plan("hotfix", {"logged_in"}) == SHIP and llm.calls == ["hotfix"] * 3, (
        "a learned decomposition saves the LLM call"
    )
    assert planner.plan("hotfix", set()) is None and planner.cached_methods == {"hotfix": tuple(SHIP)}, (
        "a reply that does not expand leaves the learned decomposition in place"
    )
    assert planner.plan("hotfix", set()) == ["login", *SHIP], "when the learned decomposition fails, ask the LLM"
    assert planner.cached_methods == {"hotfix": ("ship_change",)}, "the newest decomposition that worked is kept"

    waves = 18
    ops = dict(OPERATORS)
    methods = dict(METHODS)
    for i in range(waves):  # every wave can go out two ways, and both leave the same state
        ops[f"canary{i}"] = op(f"canary{i}", add=[f"wave{i}_live"])
        ops[f"push{i}"] = op(f"push{i}", add=[f"wave{i}_live"])
        methods[f"wave{i}"] = [
            Method(f"wave{i}_canary", f"wave{i}", (), (f"canary{i}", f"wave{i + 1}")),
            Method(f"wave{i}_push", f"wave{i}", (), (f"push{i}", f"wave{i + 1}")),
        ]
    ops["cab_signoff"] = op("cab_signoff", ["cab_approval"], ["signed_off"])  # the board never meets
    methods[f"wave{waves}"] = [Method("final_signoff", f"wave{waves}", (), ("cab_signoff",))]
    ops["push_all"] = op("push_all", add=["all_live"])
    methods["rollout"] = [
        Method("rollout_in_waves", "rollout", (), ("wave0",)),
        Method("rollout_at_once", "rollout", (), ("push_all",)),
    ]
    planner = HTNPlanner(ops, methods, ScriptedLLM({}), max_depth=64)
    start = time.perf_counter()
    found = planner.plan("rollout", set())
    elapsed = time.perf_counter() - start
    assert found == ["push_all"], "the plan behind the dead end is still found"
    assert elapsed < 0.05, "planning should stay fast when many methods lead to the same dead end"
    assert len(planner.llm.calls) == waves + 1, "a dead end costs one LLM call per search, not one per path"


@pytest.mark.skip("Part 2")
def test_method_library(tmp_path) -> None:
    """Methods, written by hand or learned from the LLM, round-trip exactly through the INI file."""
    path = str(tmp_path / "methods.ini")
    canary = Method(
        "deploy_canary",
        "deploy",
        ("artifact_built", "error_rate < 1%", "approved_by(release-eng, sre)"),
        ("push_canary", "shift_10%", "shift_100%"),
    )
    direct = Method("deploy_direct", "deploy", ("artifact_built",), ("ensure_login", "push_prod"))
    reuse = Method("reuse_session", "ensure_login", ("logged_in",), ())
    fresh = Method("fresh_login", "ensure_login", (), ("login",))
    learned = Method("hotfix_from_llm", "hotfix", (), ("ship_change", "merge"))
    note = "  Canary first, then the rest.\n# owner: release-eng\n\nShift 10%, then 100%; roll back on any alarm.\n"
    learned_note = "Learned from the LLM, kept once it expanded."

    library = MethodLibrary(path)
    assert library.entries() == [], "a new library is empty"
    library.add(canary, note=note)
    library.add(reuse)
    other = MethodLibrary(path)  # the planner service has the same file open
    other.add(fresh)
    library.add(direct)
    other.add(learned, source="llm", note=learned_note)

    expected = [
        Entry(canary, "library", note),
        Entry(reuse, "library", ""),
        Entry(fresh, "library", ""),
        Entry(direct, "library", ""),
        Entry(learned, "llm", learned_note),
    ]
    reopened = MethodLibrary(path)
    assert reopened.entries() == expected, "every method reads back exactly as it was added"
    assert reopened.methods() == {
        "deploy": [canary, direct],
        "ensure_login": [reuse, fresh],
        "hotfix": [learned],
    }, "methods are grouped by task, each task's methods in the order they were added"

    ini = configparser.ConfigParser(interpolation=None)
    ini.read(path, encoding="utf-8")
    assert ini.sections() == ["deploy_canary", "reuse_session", "fresh_login", "deploy_direct", "hotfix_from_llm"], (
        "one INI section per method, in the order they were added"
    )
    assert [(ini[name]["task"], ini[name]["source"]) for name in ini.sections()] == [
        ("deploy", "library"),
        ("ensure_login", "library"),
        ("ensure_login", "library"),
        ("deploy", "library"),
        ("hotfix", "llm"),
    ], "task and source are plain values that other tools can read"

    with pytest.raises(ValueError):
        library.add(Method("fresh_login", "log_back_in", (), ("login",)))
    with pytest.raises(ValueError):
        library.add(Method("deploy_fast", "deploy", (), ("push_prod",)), source="gpt")
    assert MethodLibrary(path).entries() == expected, "a rejected method leaves the file as it was"


def l1(genome: list[int]) -> float:
    """Distance from [3, 7], the coefficients of 3x + 7."""
    a, b = genome
    return float(abs(a - 3) + abs(b - 7))


def b_up(genome: list[int], rng: random.Random) -> list[int]:
    genome[1] += 1  # edits the genome it was handed, like a careless tool
    return genome


def a_down(genome: list[int], rng: random.Random) -> list[int]:
    return [genome[0] - 1, genome[1]]


def sse(genome: list[int]) -> float:
    """The lesson's evaluator: squared error against 3x + 7 on x = -5..5."""
    a, b = genome
    return float(sum((3 * x + 7 - (a * x + b)) ** 2 for x in range(-5, 6)))


def nudge(genome: list[int], rng: random.Random) -> list[int]:
    i = rng.randrange(len(genome))
    genome[i] += rng.choice((-1, 1))  # in place, too
    return genome


def jump(genome: list[int], rng: random.Random) -> list[int]:
    """The lesson's random_mutation."""
    return [v + rng.choice((-2, -1, 0, 1, 2)) for v in genome]


SEEDED_RUN = [  # (generation, best, fitness, evaluations, cache hits) for seed 11
    (0, [0, 0], 1529.0, 1, 0),
    (1, [2, 0], 649.0, 3, 0),
    (2, [2, 1], 506.0, 7, 2),
    (3, [4, 2], 385.0, 9, 6),
    (4, [3, 2], 275.0, 14, 7),
    (5, [4, 4], 209.0, 19, 8),
    (6, [3, 3], 176.0, 24, 9),
    (7, [3, 3], 176.0, 26, 13),
    (8, [3, 4], 99.0, 27, 18),
    (9, [3, 4], 99.0, 29, 22),
    (10, [3, 7], 0.0, 34, 23),
]


@pytest.mark.skip("Part 3")
def test_evolve() -> None:
    """A seeded search is exact: the same generations, the same evaluations, the same cache hits."""
    seen: list[tuple[int, ...]] = []

    def scored(genome: list[int]) -> float:
        seen.append(tuple(genome))
        return l1(genome)

    seed_genome = [5, 5]
    history = evolve(seed_genome, scored, [b_up, a_down], seed=0, generations=10, survivors=2, target=0.0)
    assert seed_genome == [5, 5], "the seed genome is never edited"
    assert [(g.number, g.best, g.fitness) for g in history] == [
        (0, [5, 5], 4.0),
        (1, [4, 5], 3.0),
        (2, [3, 5], 2.0),
        (3, [3, 6], 1.0),
        (4, [3, 7], 0.0),
    ], "keep the best distinct genomes, ties broken by the genome, until a generation reaches the target"
    assert [(g.evaluations, g.cache_hits) for g in history] == [(1, 0), (3, 0), (6, 1), (9, 2), (12, 3)], (
        "evaluations and cache hits so far, generation by generation"
    )
    assert len(seen) == len(set(seen)) == 12, "the evaluator runs once per distinct genome"
    assert len(evolve([3, 7], l1, [b_up, a_down], seed=0, generations=5, target=0.0)) == 1, (
        "a seed that already meets the target ends the run"
    )
    assert [g.number for g in evolve([5, 5], l1, [b_up, a_down], seed=0, generations=2)] == [0, 1, 2], (
        "generations counts the generations after the seed"
    )

    cut = evolve([5, 5], l1, [b_up, a_down], seed=0, generations=10, survivors=2, budget=7)
    assert [(g.number, g.best, g.evaluations, g.cache_hits) for g in cut] == [
        (0, [5, 5], 1, 0),
        (1, [4, 5], 3, 0),
        (2, [3, 5], 6, 1),
        (3, [3, 6], 7, 1),
    ], "only evaluator calls count against the budget, and the search stops the moment it is spent"
    cut = evolve([5, 5], l1, [b_up, a_down], seed=0, generations=10, survivors=2, budget=6)
    assert [(g.number, g.evaluations, g.cache_hits) for g in cut][-1] == (2, 6, 0), (
        "nothing is mutated once the budget is spent"
    )
    cut = evolve([5, 5], l1, [b_up, a_down], seed=0, generations=10, survivors=2, budget=5)
    assert [(g.number, g.best) for g in cut][-1] == (2, [3, 5]), (
        "each parent, best first, goes through every mutator before the next parent"
    )

    before = random.getstate()
    runs = [evolve([0, 0], sse, [nudge, jump], seed=11, generations=12, target=0.0) for _ in range(2)]
    assert random.getstate() == before, "the search leaves the global random generator alone"
    assert runs[0] == runs[1], "the same seed gives the same run"
    assert [(g.number, g.best, g.fitness, g.evaluations, g.cache_hits) for g in runs[0]] == SEEDED_RUN, (
        "each mutation draws from the generator the docstring names"
    )
    assert all(b.fitness <= a.fitness for a, b in zip(runs[0], runs[0][1:])), "the best never gets worse"


def run_stream(agen) -> tuple[list[str], int]:
    """Drain an async stream, then count the tasks it left running."""

    async def drain() -> tuple[list[str], int]:
        lines = [line async for line in agen]
        others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        return lines, len(others)

    return asyncio.run(asyncio.wait_for(drain(), 2.0))


def mae(genome: list[int]) -> float:
    """Mean absolute error against 3x + 7 on x = -5..5."""
    a, b = genome
    return sum(abs(3 * x + 7 - (a * x + b)) for x in range(-5, 6)) / 11


@pytest.mark.skip("Part 4")
def test_stream_generations() -> None:
    """Mutators work concurrently, the evaluator one child at a time, and each generation is a CSV line."""
    expected = [
        (g.number, g.best, g.fitness, g.evaluations, g.cache_hits)
        for g in evolve([0, 0], mae, [nudge, jump], seed=10, generations=8, budget=22)
    ]
    running = peak = overlaps = 0
    busy = False

    async def score(genome: list[int]) -> float:
        nonlocal busy, overlaps
        overlaps += busy
        busy = True
        await asyncio.sleep(0)  # the benchmark takes a turn of the event loop
        busy = False
        return mae(genome)

    def model(mutate, latency: int):
        async def propose(genome: list[int], rng: random.Random) -> list[int]:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            try:
                for _ in range(latency):
                    await asyncio.sleep(0)
                return mutate(genome, rng)
            finally:
                running -= 1

        return propose

    for latencies in ((1, 9), (9, 1)):  # which model answers first
        ensemble = [model(nudge, latencies[0]), model(jump, latencies[1])]
        lines, _ = run_stream(stream_generations([0, 0], score, ensemble, seed=10, generations=8, budget=22))
        assert lines[0].rstrip("\r\n") == "gen,best_genome,best_fitness,evaluations,cache_hits", (
            "the first line is the CSV header"
        )
        assert all(line.endswith("\n") for line in lines), "every line ends with a line break"
        rows = list(csv.DictReader(io.StringIO("".join(lines))))
        got = [
            (
                int(row["gen"]),
                json.loads(row["best_genome"]),
                float(row["best_fitness"]),
                int(row["evaluations"]),
                int(row["cache_hits"]),
            )
            for row in rows
        ]
        assert got == expected, (
            "the same generations as evolve(), the one the budget cut short too, whichever model answers first"
        )
    assert peak == 6, "all mutations of a generation run at the same time"
    assert overlaps == 0, "the evaluator scores one child at a time"

    hung: list[str] = []

    async def stuck(genome: list[int], rng: random.Random) -> list[int]:  # a model that never answers
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0)  # it closes its connection before it gives up
            hung.append("cancelled")
            raise
        return genome

    ensemble = [model(jump, 1), stuck]
    lines, leftover = run_stream(stream_generations([0, 0], score, ensemble, seed=10, generations=3, budget=2))
    assert len(lines) == 3 and (leftover, hung) == (0, ["cancelled"]), (
        "a mutation still running when the budget runs out is cancelled"
    )

    started: list[int] = []

    async def counting(genome: list[int], rng: random.Random) -> list[int]:
        started.append(1)
        return jump(genome, rng)

    async def first_lines() -> tuple[int, int]:
        agen = stream_generations([0, 0], score, [counting, counting], seed=10, generations=8)
        await agen.__anext__()  # the header
        await agen.__anext__()  # generation 0, the seed
        before = len(started)
        await agen.__anext__()
        after = len(started)
        await agen.aclose()
        return before, after

    assert asyncio.run(first_lines()) == (0, 2), "each generation's line comes out before the next one starts"


@pytest.mark.skip("Part 5")
def test_task_tree() -> None:
    """The planner hands back its decomposition tree, and an independent check replays it."""
    planner = HTNPlanner(OPERATORS, METHODS, ScriptedLLM({"hotfix": [("ship_change", "merge")]}))
    state = {"reviewer_online", "canary_cluster"}
    tree = planner.plan_tree("release", state)
    assert tree == Node(
        "release",
        "release_m1",
        (
            Node(
                "ship_change",
                "ship_change_m1",
                (
                    Node("ensure_login", "fresh_login", (Node("login"),)),
                    Node("open_editor"),
                    Node("write_tests"),
                    Node("run_tests"),
                    Node("open_pr"),
                ),
            ),
            Node("merge", "merge_reviewed", (Node("request_review"), Node("merge_pr"))),
            Node("build"),
            Node("deploy", "deploy_direct", (Node("ensure_login", "reuse_session"), Node("push_prod"))),
        ),
    ), "every compound task records the method that worked for it"
    assert leaves(tree) == planner.plan("release", state), "the plan is the tree's leaves, left to right"

    hotfix = planner.plan_tree("hotfix", state)
    assert (hotfix.method, [child.task for child in hotfix.children]) == ("llm", ["ship_change", "merge"]), (
        "a decomposition from the LLM is marked llm"
    )
    assert planner.plan_tree("hotfix", state) == hotfix and planner.llm.calls == ["hotfix"], (
        "a learned decomposition is marked llm too"
    )

    assert check(tree, OPERATORS, METHODS, state) is None, "the planner's tree replays"
    assert check(hotfix, OPERATORS, METHODS, state) is None, "so does a tree with an llm node"
    assert state == {"reviewer_online", "canary_cluster"}, "the check replays on its own copy of the state"
    assert check(tree, OPERATORS, METHODS, {"canary_cluster"}) == (1, 0), (
        "replay from the state you are given: there, request_review cannot run"
    )
    assert check(tree.children[1], OPERATORS, METHODS, set()) == (), "the root is checked like any other node"

    def release_shipping(*steps: Node) -> Node:
        """The release tree with ship_change decomposed into these steps instead."""
        return Node("release", "release_m1", (Node("ship_change", "ship_change_m1", steps), *tree.children[1:]))

    login, editor, tests, *rest = tree.children[0].children
    swapped = release_shipping(login, tests, editor, *rest)
    assert check(swapped, OPERATORS, METHODS, state) == (0,), "a method's node has exactly the method's subtasks"
    relabeled = release_shipping(Node("ensure_login", "reuse_session"), editor, tests, *rest)
    assert check(relabeled, OPERATORS, METHODS, state) == (0, 0), "a method's preconditions must hold too"
    twice = Node("merge", "llm", (Node("request_review"), Node("merge_pr"), Node("merge_pr")))
    assert check(twice, OPERATORS, METHODS, {"pr_open", "reviewer_online"}) == (2,), (
        "of two identical steps, the second one is the one that fails"
    )
    invented = Node("hotfix", "llm", (Node("open_editor"), Node("revert_db", "llm", (Node("login"),))))
    assert check(invented, OPERATORS, METHODS, {"logged_in"}) == (1,), (
        "an llm node may only use operators and library tasks"
    )
    stolen = Node("deploy", "merge_reviewed", (Node("request_review"), Node("merge_pr")))
    assert check(stolen, OPERATORS, METHODS, {"pr_open", "reviewer_online"}) == (), (
        "a method only decomposes its own task"
    )
    bare = Node("redeploy", "redeploy_existing", (Node("deploy"),))
    assert check(bare, OPERATORS, METHODS, {"artifact_built", "logged_in"}) == (0,), (
        "a compound task needs a decomposition"
    )
    assert check(Node("login", "llm", (Node("push_prod"),)), OPERATORS, METHODS, set()) == (), (
        "an operator node has no method and no children"
    )
