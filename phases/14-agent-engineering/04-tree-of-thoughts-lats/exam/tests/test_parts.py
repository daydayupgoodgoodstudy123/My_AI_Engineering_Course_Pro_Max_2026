import asyncio
import json
import math
import time
from fractions import Fraction

import pytest
from thoughtree.checkpoint import MAGIC, VERSION, load, save
from thoughtree.expr import Leaf, Op, build, evaluate, render
from thoughtree.game import Step, children, combine, solvable, start, value
from thoughtree.mcts import run, uct
from thoughtree.service import Solver
from thoughtree.stream import stream_tot
from thoughtree.tot import tot_bfs
from thoughtree.tree import Node, Search


def steps(trace: list[Step] | None) -> list[str] | None:
    return None if trace is None else [str(step) for step in trace]


def step(a, op: str, b) -> Step:
    a, b = Fraction(a), Fraction(b)
    return Step(a, op, b, combine(a, op, b))


def numbers(*xs) -> tuple[Fraction, ...]:
    return tuple(Fraction(x) for x in xs)


def walk(node: Node):
    yield node
    for child in node.children:
        yield from walk(child)


@pytest.mark.skip("Part 1")
def test_tot_search() -> None:
    """ToT finds exact solutions, keeps distinct states in its beam, and says when there is none."""
    trace = tot_bfs([4, 4, 10, 10])
    assert trace is not None and [s.result for s in trace] == [100, 96, 24], (
        "a solution goes on until 24 is the only number left"
    )
    assert steps(tot_bfs([3, 3, 8, 8])) == ["8 / 3 = 8/3", "3 - (8/3) = 1/3", "8 / (1/3) = 24"], (
        "8 / (3 - 8 / 3) is exactly 24"
    )
    assert steps(trace) == ["10 * 10 = 100", "100 - 4 = 96", "96 / 4 = 24"], "(10 * 10 - 4) / 4"
    assert steps(tot_bfs([4, 6, 4, 1])) == ["6 + 1 = 7", "7 * 4 = 28", "28 - 4 = 24"], (
        "the lesson's deal: 6 * 4 = 24 leaves (24, 4, 1), a dead end"
    )
    assert steps(tot_bfs([1, 5, 5, 5])) == ["1 / 5 = 1/5", "5 - (1/5) = 24/5", "5 * (24/5) = 24"], (
        "5 * (5 - 1 / 5) is a solution too"
    )
    assert steps(tot_bfs([1, 2, 3, 8])) == ["8 + 3 = 11", "11 + 1 = 12", "12 * 2 = 24"], (
        "states with the same score keep the order they were found in"
    )
    assert [str(s) for s, _ in children(start([5, 1]))] == [
        "5 + 1 = 6", "5 - 1 = 4", "1 - 5 = -4", "5 * 1 = 5", "5 / 1 = 5", "1 / 5 = 1/5",
    ], "+ and * give one child per pair; - and / give one for each order"
    assert len(children(start([4, 6, 4, 1]))) == 36, "4 numbers make 6 pairs of 6 children"
    assert tot_bfs([1, 1, 1, 1]) is None, "a deal with no solution has no answer"

    began = time.perf_counter()
    for deal in ([7] * 5, [9] * 5, [10] * 5):
        assert tot_bfs(deal, beam=None) is None, "plain BFS shows these deals have no solution"
    assert time.perf_counter() - began < 0.15, "plain BFS should stay fast when many paths reach the same states"

    assert solvable(start([1, 2, 3, 4, 6, 11])) and tot_bfs([1, 2, 3, 4, 6, 11]) is None, (
        "the beam keeps 5 states per level, and with six numbers the judge can only guess, so ToT misses this one"
    )

    assert steps(tot_bfs([1, 5, 5, 5, 13])) == ["5 + 5 = 10", "13 - 1 = 12", "12 * 10 = 120", "120 / 5 = 24"], (
        "copies of one state must not crowd the beam"
    )
    assert steps(tot_bfs([5, 6, 6, 6, 7, 10])) == [
        "10 + 7 = 17", "17 + 5 = 22", "6 + 6 = 12", "12 / 6 = 2", "22 + 2 = 24",
    ], "a state that two parents reach is kept once as well"


@pytest.mark.skip("Part 2")
def test_checkpoint_roundtrip() -> None:
    """A search survives a checkpoint exactly, and anything that is not a checkpoint is refused."""
    root = Node(numbers(6, 4, 4, 1), [], visits=1_000_003, value_sum=0.1 + 0.2)
    # 6 * 4 = 24 twice (the deal has two 4s), then 4 / 6 = 2/3
    for s, state, visits, value_sum in (
        (step(6, "*", 4), numbers(24, 4, 1), 7, 1 / 3),
        (step(6, "*", 4), numbers(24, 4, 1), 2, 2.5e-310),
        (step(4, "/", 6), numbers(4, 1, Fraction(2, 3)), 70_000, -12345.678),
    ):
        root.children.append(Node(state, [s], visits, value_sum))
    below = root.children[2]
    for s, state in (
        (step(Fraction(2, 3), "-", 4), numbers(1, Fraction(-10, 3))),
        (step(Fraction(2, 3), "-", 1), numbers(4, Fraction(-1, 3))),
        (step(4, "/", 1), numbers(4, Fraction(2, 3))),  # 4 * 1 = 4 reaches the same state
    ):
        below.children.append(Node(state, below.trace + [s], 1, 0.7))
    solution = [step(6, "+", 1), step(7, "*", 4), step(28, "-", 4)]
    search = Search(root, seed=-7, c=2**0.5, iterations=1_000_003, solution=solution)

    blob = save(search)
    assert blob[:6] == MAGIC + VERSION.to_bytes(2, "little"), "a checkpoint starts with MAGIC and VERSION"
    restored = load(blob)
    assert restored == search, "a search must round-trip exactly"
    assert all(type(x) is Fraction for node in walk(restored.root) for x in node.state), (
        "numbers come back as Fractions"
    )
    assert all(type(node.visits) is int for node in walk(restored.root)), "visits come back as ints"
    assert type(restored.seed) is int and type(restored.iterations) is int, (
        "the seed and the iteration count come back as ints"
    )
    assert save(restored) == blob, "saving a loaded search gives the same bytes"

    big = Search(Node(numbers(1_000_033, 1_000_003, 7, 1), []), seed=2**40)
    # 1000033 * 1000003 does not fit in 32 bits
    big.root.children.append(Node(numbers(1_000_036_000_099, 7, 1), [step(1_000_033, "*", 1_000_003)], 1, 0.5))
    assert load(save(big)) == big, "a search must round-trip exactly"
    done = Search(Node(numbers(24), []), seed=0, iterations=1, solution=[])
    assert load(save(done)).solution == [], "a deal that is already 24 has an empty solution, which is not None"
    huge = Search(Node(numbers(2**40, 2**40, 1, 1), []), seed=0)
    huge.root.children.append(Node(numbers(2**80, 1, 1), [step(2**40, "*", 2**40)]))
    with pytest.raises(ValueError):
        save(huge)

    for broken in (blob + b"\x00", b"STAL" + blob[4:], MAGIC + (VERSION + 1).to_bytes(2, "little") + blob[6:]):
        with pytest.raises(ValueError):
            load(broken)
    for cut in range(len(blob)):
        with pytest.raises(ValueError):
            load(blob[:cut])


@pytest.mark.skip("Part 3")
def test_mcts_search() -> None:
    """LATS-style MCTS: UCT selection, lazy expansion, seeded rollouts, and a search that can resume."""
    parent = Node(start([4, 6, 4, 1]), [], visits=10)
    child = Node(start([24, 4, 1]), [], visits=4, value_sum=1.0)
    assert uct(parent, child, 1.4) == pytest.approx(0.25 + 1.4 * math.sqrt(math.log(10) / 4)), (
        "UCT is Q + c * sqrt(ln N / n)"
    )
    assert uct(parent, Node(start([10, 4, 1]), []), 1.4) == math.inf, "a child never visited is tried first"

    pair = Search.new([5, 4], seed=0)
    assert run(pair, 4) is None and [child.visits for child in pair.root.children] == [1, 1, 1, 0, 0, 0], (
        "the root is rolled out once and then expanded; its children are tried in order"
    )
    assert run(pair, 26) is None and pair.iterations == 30, "5 and 4 cannot make 24"
    assert [child.visits for child in pair.root.children] == [5, 5, 4, 6, 5, 4], (
        "UCT weighs a child's mean reward against how often it was tried"
    )
    assert all(not child.children for child in pair.root.children), "a finished node is never expanded"

    greedy, curious = Search.new([1, 2, 7], seed=0, c=0.1), Search.new([1, 2, 7], seed=0, c=2.0)
    assert run(greedy, 100) is None and run(curious, 100) is None, "1, 2 and 7 cannot make 24"
    assert [child.visits for child in greedy.root.children] == [
        5, 4, 4, 7, 4, 4, 7, 4, 4, 6, 4, 5, 20, 5, 4, 4, 4, 4,
    ], "with a small c, UCT keeps going back to 2 + 1 = 3, where 7 * 3 = 21 comes close"
    assert [child.visits for child in curious.root.children] == [
        6, 5, 5, 6, 5, 5, 6, 6, 5, 6, 6, 5, 6, 5, 5, 6, 6, 5,
    ], "with a large c, UCT spreads its visits"
    small = Search.new([2, 3], seed=0, c=0.1)
    assert run(small, 70) is None and [child.visits for child in small.root.children] == [14, 10, 9, 15, 11, 10], (
        "a visit counts once its reward is backpropagated"
    )

    search = Search.new([4, 6, 4, 1], seed=9)
    assert steps(run(search, 1000)) == ["6 - 1 = 5", "5 * 4 = 20", "20 + 4 = 24"], (
        "a rollout that reaches 24 is the answer"
    )
    assert search.iterations == 150 and search.root.visits == 150, "the search stops at its first solution"
    assert run(search, 10) == search.solution and search.iterations == 150, "a solved search runs no more"
    done = Search.new([24], seed=0)
    assert run(done, 5) == [] and done.iterations == 1, "a deal that is already 24 is solved by its first rollout"

    first = Search.new([4, 6, 4, 1], seed=9)
    run(first, 60)
    resumed = load(save(first))
    run(resumed, 1000)
    assert save(resumed) == save(search), "a resumed search ends exactly where an uninterrupted one does"


class FakeJudge:
    """An LLM judge stand-in: a verdict on the state (game.value's by default), a number of event-loop
    turns later.

    It answers the newest question first: call k (counting from 0) waits 5 * (100 - k) turns.
    A call costs 20 tokens plus 10 for every number in the state.
    """

    def __init__(self, verdict=value) -> None:
        self.verdict = verdict
        self.calls = 0
        self.running = self.peak = 0
        self.finished: list[list[str]] = []
        self.cancelled: list[list[str]] = []

    async def __call__(self, state):
        k = self.calls
        self.calls += 1
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            for _ in range(5 * (100 - k)):
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            for _ in range(3):  # hanging up on the model takes a few turns as well
                await asyncio.sleep(0)
            self.cancelled.append([str(x) for x in state])
            raise
        finally:
            self.running -= 1
        self.finished.append([str(x) for x in state])
        return self.verdict(state), 20 + 10 * len(state)


def judged(numbers: list[int], budget: int, beam: int = 5, verdict=value):
    """Stream a search to the end: the lines, how many judgements had come back when each line
    arrived, the judge, and how many tasks were still running when the stream ended."""

    async def main():
        judge = FakeJudge(verdict)
        chunks: list[str] = []
        back: list[int] = []
        async for chunk in stream_tot(numbers, judge, budget, beam):
            chunks.append(chunk)
            back += [len(judge.finished)] * chunk.count("\n")
        leftover = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        for _ in range(1000):
            await asyncio.sleep(0)
        return chunks, back, judge, len(leftover)

    chunks, back, judge, leftover = asyncio.run(main())
    lines = [json.loads(line) for line in "".join(chunks).splitlines()]
    return lines, back, judge, leftover


@pytest.mark.skip("Part 4")
def test_stream_judging() -> None:
    """Judgements run concurrently and stream as they come back; the search stops on an answer or the budget."""
    lines, back, judge, leftover = judged([4, 6], budget=1000)
    assert lines == [
        {"depth": 1, "state": ["2/3"], "value": 0.0, "tokens_used": 30},
        {"depth": 1, "state": ["3/2"], "value": 0.0, "tokens_used": 60},
        {"depth": 1, "state": ["24"], "value": 1.0, "tokens_used": 90},
        {"stop": "solved", "tokens_used": 90, "trace": ["6 * 4 = 24"]},
    ], "one line per judgement in the order they come back, then the stop line"
    assert back == [1, 2, 3, 3], "every judgement is streamed the moment it comes back"
    assert judge.peak == 6, "all the states of a level are judged at once"
    assert sorted(judge.cancelled) == [["-2"], ["10"], ["2"]] and judge.finished == [["2/3"], ["3/2"], ["24"]], (
        "the judgements still running when the search stops are cancelled"
    )
    assert leftover == 0, "no judgement outlives the stream"

    lines, _, judge, leftover = judged([4, 6], budget=60)
    assert lines[2:] == [{"stop": "budget", "tokens_used": 60}], "the search stops as soon as the budget is spent"
    assert len(judge.cancelled) == 4 and leftover == 0, (
        "the judgements still running when the budget runs out are cancelled"
    )
    assert judged([4, 6], budget=90)[0][-1]["stop"] == "solved", "an answer found with the last tokens still counts"
    assert judged([4, 6], budget=50)[0][2:] == [{"stop": "budget", "tokens_used": 60}], (
        "the stop line reports what was spent, even past the budget"
    )

    lines, back, judge, leftover = judged([2, 3, 4], budget=10_000, beam=2)
    assert [line["state"] for line in lines if line.get("depth") == 1] == [
        ["4", "2/3"], ["4", "3/2"], ["6", "4"], ["4", "-1"], ["4", "1"], ["5", "4"], ["3", "1/2"], ["8", "3"],
        ["3", "-2"], ["3", "2"], ["6", "3"], ["2", "3/4"], ["2", "4/3"], ["12", "2"], ["2", "-1"], ["2", "1"],
        ["7", "2"],
    ], "every distinct state of a level is judged once"
    assert [line["state"] for line in lines if line.get("depth") == 2] == [
        ["3/8"], ["8/3"], ["-5"], ["5"], ["11"], ["1/6"], ["6"], ["24"],
    ], "the next level grows from the beam best states, ties in the order they were found"
    assert judge.peak == 17 and back == [*range(1, 26), 25], (
        "a level is judged all at once and streamed as it comes back"
    )
    assert [line["tokens_used"] for line in lines] == [*range(40, 681, 40), *range(710, 921, 30), 920], (
        "tokens_used adds up the judgements that came back"
    )
    assert lines[-1] == {"stop": "solved", "tokens_used": 920, "trace": ["4 * 3 = 12", "12 * 2 = 24"]}, (
        "the stop line carries the first path that reached 24"
    )
    assert sorted(judge.cancelled) == [["-10"], ["10"], ["14"]] and leftover == 0, (
        "the judgements still running when the search stops are cancelled"
    )

    lines, _, _, leftover = judged([1, 1, 1], budget=10_000, beam=2)
    assert [line.get("state") for line in lines] == [
        ["1", "1"], ["1", "0"], ["2", "1"], ["0"], ["1/2"], ["2"], ["-1"], ["1"], ["3"], None,
    ] and lines[-1] == {"stop": "exhausted", "tokens_used": 300}, "the stream ends when nothing is left to judge"

    lines, _, _, _ = judged([2, 3, 4], budget=10_000, beam=1, verdict=lambda state: 1 - value(state))
    assert [line["state"] for line in lines if line.get("depth") == 2] == [
        ["2/7"], ["7/2"], ["14"], ["-5"], ["5"], ["9"],
    ] and lines[-1] == {"stop": "exhausted", "tokens_used": 860}, (
        "the beam follows the judge's verdicts, right or wrong"
    )

    lines, _, judge, _ = judged([24], budget=100)
    assert lines == [{"stop": "solved", "tokens_used": 0, "trace": []}] and judge.calls == 0, (
        "a deal that is already 24 needs no judgement"
    )


@pytest.mark.skip("Part 5")
def test_expression_tree() -> None:
    """A solution's steps become one expression tree, written with the fewest parentheses."""
    lesson = build([4, 6, 4, 1], [step(6, "+", 1), step(7, "*", 4), step(28, "-", 4)])
    assert lesson == Op("-", Op("*", Op("+", Leaf(6, 1), Leaf(1, 3)), Leaf(4, 0)), Leaf(4, 2)), (
        "every number of the deal is its own leaf, used once"
    )
    assert render(lesson) == "(6 + 1) * 4 - 4" and evaluate(lesson) == 24, "(6 + 1) * 4 - 4 is 24"
    tens = build([4, 4, 10, 10], [step(10, "*", 10), step(100, "-", 4), step(96, "/", 4)])
    assert tens == Op("/", Op("-", Op("*", Leaf(10, 2), Leaf(10, 3)), Leaf(4, 0)), Leaf(4, 1)), (
        "a step takes its a first, then its b from what is left"
    )
    assert render(tens) == "(10 * 10 - 4) / 4", "(10 * 10 - 4) / 4 is 24"
    exact = build([3, 3, 8, 8], [step(8, "/", 3), step(3, "-", Fraction(8, 3)), step(8, "/", Fraction(1, 3))])
    assert render(exact) == "8 / (3 - 8 / 3)" and evaluate(exact) == 24, "8 / (3 - 8 / 3) is exactly 24"
    negative = build([4, 6, 4, 1], [step(1, "-", 6), step(4, "*", -5), step(4, "-", -20)])
    assert render(negative) == "4 - 4 * (1 - 6)" and evaluate(negative) == 24, "1 - 6 is not 6 - 1"
    pooled = build([2, 3, 6, 6], [step(6, "/", 3), step(2, "*", 6), step(12, "*", 2)])
    assert pooled == Op("*", Op("*", Leaf(2, 0), Leaf(6, 3)), Op("/", Leaf(6, 2), Leaf(3, 1))), (
        "an operand comes from the earliest place in the pool that holds its value"
    )
    assert build([24], []) == Leaf(24, 0) and render(Leaf(24, 0)) == "24", "a deal of one number is that number"

    ten, three, one = Leaf(10, 0), Leaf(3, 1), Leaf(1, 2)
    assert [
        render(Op("-", ten, Op("-", three, one))),
        render(Op("-", Op("-", ten, three), one)),
        render(Op("+", ten, Op("-", three, one))),
        render(Op("/", ten, Op("*", three, one))),
        render(Op("*", ten, Op("/", three, one))),
        render(Op("*", Op("+", ten, three), one)),
    ] == ["10 - (3 - 1)", "10 - 3 - 1", "10 + 3 - 1", "10 / (3 * 1)", "10 * 3 / 1", "(10 + 3) * 1"], (
        "parentheses only where the meaning needs them"
    )
    assert evaluate(build([1, 3], [step(1, "/", 3)])) == Fraction(1, 3), "evaluate returns the exact Fraction"

    for deal, trace in (
        ([4, 6, 4, 1], [step(1, "/", 5), step(5, "-", Fraction(1, 5)), step(5, "*", Fraction(24, 5))]),  # no 5s here
        ([3, 8], [Step(Fraction(8), "/", Fraction(3), Fraction(3))]),  # 8 / 3 is not 3
        ([4, 6, 4, 1], [step(6, "+", 1), step(7, "*", 4)]),  # stops before every number is used
    ):
        with pytest.raises(ValueError):
            build(deal, trace)
    assert Solver().answer([1, 5, 5, 5]) == "5 * (5 - 1 / 5)", "the service writes ToT's answer as one expression"
