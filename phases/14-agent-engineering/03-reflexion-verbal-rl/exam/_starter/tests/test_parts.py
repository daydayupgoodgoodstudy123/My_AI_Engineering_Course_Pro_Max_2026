import asyncio
import csv
import io
import time

import pytest
from reflexion.curve import learning_curve
from reflexion.judge import Trial, judge, run_trials
from reflexion.learnings import HEADER, read_learnings, write_learnings
from reflexion.memory import EpisodicMemory, Reflection
from reflexion.puzzle import ToolDown, run_reflexion, scalar_check
from reflexion.scope import Recalled, ScopeTree


def raises(error, action, *args, **kwargs) -> bool:
    try:
        action(*args, **kwargs)
    except error:
        return True
    return False


SHORT = [
    "tried [1, 2, 3]: sum 6 is 14 short; pick larger values",
    "tried [5, 2, 3]: sum 10 is 10 short; pick larger values",
    "tried [9, 2, 3]: sum 14 is 6 short; pick larger values",
    "tried [9, 6, 3]: sum 18 is 2 short; pick larger values",
]


@pytest.mark.skip("Part 1")
def test_reflexion_loop() -> None:
    """Reflections point the right way, the buffer keeps the newest ones, outages teach nothing, and a big buffer stays fast."""
    results = run_reflexion(20, max_trials=6)
    assert [(r.attempt, r.delta) for r in results] == [
        ([1, 2, 3], -14),
        ([5, 2, 3], -10),
        ([9, 2, 3], -6),
        ([9, 6, 3], -2),
        ([9, 8, 3], 0),
    ], "reflexion should converge on a reachable target"
    assert [r.reflection for r in results] == SHORT + [None], "each miss gets a one-line diagnosis; the success gets none"

    small = EpisodicMemory(max_len=2)
    results = run_reflexion(20, max_trials=6, memory=small)
    assert [r.attempt for r in results] == [[1, 2, 3], [5, 2, 3], [9, 2, 3], [9, 6, 3], [9, 8, 3]], (
        "a small buffer still converges: the actor reads the newest reflection"
    )
    assert [r.trial for r in small.reflections()] == [3, 4], "a full buffer drops its oldest reflection"

    memory = EpisodicMemory(max_len=3)
    memory.add(Reflection(1, "math/arith/sum", "Pick larger values when the sum is short."))
    memory.add(Reflection(2, "math/arith/sum", "Start from the largest number."))
    memory.add(Reflection(4, "math/arith/sum", "pick larger values  when the SUM is short. ", ttl=5, failures=2))
    assert memory.reflections() == [
        Reflection(2, "math/arith/sum", "Start from the largest number."),
        Reflection(4, "math/arith/sum", "pick larger values  when the SUM is short. ", ttl=5, failures=3),
    ], "a lesson learned again moves to the newest slot with its latest trial, wording and ttl, and counts both failures"
    memory.add(Reflection(5, "math/arith/sum", "Stop raising a number at nine."))
    memory.add(Reflection(6, "math/arith/sum", "Check the sum before answering."))
    assert [r.trial for r in memory.reflections()] == [4, 5, 6], "a full buffer drops its oldest reflection"
    memory.add(Reflection(7, "math/arith/sum", "start from the largest number."))
    assert [(r.trial, r.failures) for r in memory.reflections()] == [(5, 1), (6, 1), (7, 1)], (
        "a dropped lesson can be learned again, from scratch"
    )
    memory.add(Reflection(8, "math/arith/sum", "check the sum before answering."))
    assert [(r.trial, r.failures) for r in memory.reflections()] == [(5, 1), (7, 1), (8, 2)], (
        "a lesson learned again on a full buffer pushes nothing out"
    )

    calls: list[list[int]] = []

    def flaky(attempt: list[int], target: int) -> int:
        calls.append(attempt)
        if len(calls) == 3:
            raise ToolDown("calculator service unavailable")
        return scalar_check(attempt, target)

    memory = EpisodicMemory()
    results = run_reflexion(20, max_trials=6, memory=memory, check=flaky)
    assert [(r.trial, r.attempt, r.delta, r.reflection) for r in results] == [
        (1, [1, 2, 3], -14, SHORT[0]),
        (2, [5, 2, 3], -10, SHORT[1]),
        (3, [9, 2, 3], None, None),
        (4, [9, 2, 3], -6, SHORT[2]),
        (5, [9, 6, 3], -2, SHORT[3]),
        (6, [9, 8, 3], 0, None),
    ], "an external failure teaches nothing: it costs a trial, not what was learned"
    assert [r.trial for r in memory.reflections()] == [1, 2, 4, 5], "only the agent's own misses are stored"

    def down(attempt: list[int], target: int) -> int:
        calls.append(attempt)
        if len(calls) > 20:
            raise AssertionError("each trial runs its check once")
        raise ToolDown("calculator service unavailable")

    calls.clear()
    memory = EpisodicMemory()
    results = run_reflexion(20, max_trials=3, memory=memory, check=down)
    assert [(r.trial, r.success, r.reflection) for r in results] == [(1, False, None), (2, False, None), (3, False, None)], (
        "every trial counts, even while the tool stays down"
    )
    assert len(memory) == 0 and len(calls) == 3, "every trial counts, even while the tool stays down"

    def broken(attempt: list[int], target: int) -> int:
        raise TypeError("checker bug: unsupported operand")

    assert raises(TypeError, run_reflexion, 20, check=broken), "a bug in the checker is not an outage"

    replay = EpisodicMemory(max_len=5000)
    log = [
        Reflection(n, "code/tests", f"Patch {n % 3600} broke test_case_{n % 3600}: run it before editing")
        for n in range(1, 3701)
    ]
    start = time.perf_counter()
    for reflection in log:
        replay.add(reflection)
    elapsed = time.perf_counter() - start
    kept = replay.reflections()
    assert (len(kept), kept[0].trial, kept[-1].trial, kept[-1].failures) == (3600, 101, 3700, 2), (
        "replaying a long run keeps one entry per lesson, newest last"
    )
    assert elapsed < 0.1, "adding to a big buffer should stay fast"


FIRST = Reflection(3, "math/arith/sum", SHORT[0])
FENCED = Reflection(8, "code/tests", "Run ``` blocks through the doc tests too.", ttl=5, failures=2)

# Reflection texts that a Markdown file can easily get wrong.
TEXTS = [
    "Run `pytest -x` first.\nThe failing test names the file to open.",
    "- read the traceback\n- then open the file it names",
    "# Root cause\nI patched the caller instead of the parser.",
    "## code/tests (trial 1, ttl 10, failures 1)\nI pasted the learnings file into my answer.",
    "My patch added a fenced example:\n```python\nprint(parse('1,2'))\n```\nand broke the docs build.",
    "````\nfour backticks on a line of their own\n````",
    "```",
    "Two trailing spaces are a Markdown line break  \nso keep them  ",
    "    return parse(text)\nwas indented four spaces, so Markdown shows it as code",
    "\nThe text starts with a blank line and ends with one.\n",
    "Tabs\tstay tabs, and a run of   spaces stays a run.",
    "Arthur's Magazine (1844) came before First for Women (1989): compare the years.",
    "先运行失败的测试，再改代码。",
]


@pytest.mark.skip("Part 2")
def test_learnings_file(tmp_path) -> None:
    """Reflections round-trip through a Markdown learnings file that people read and edit."""
    path = tmp_path / "LEARNINGS.md"
    assert read_learnings(path) == [], "no file yet, no learnings"
    write_learnings(path, [FIRST, FENCED])
    assert path.read_bytes().decode("utf-8") == (
        HEADER
        + "\n## math/arith/sum (trial 3, ttl 10, failures 1)\n\n```\n"
        + FIRST.text
        + "\n```\n\n## code/tests (trial 8, ttl 5, failures 2)\n\n````\n"
        + FENCED.text
        + "\n````\n"
    ), "the layout in the module docstring: a heading, a blank line, the text in a fence that can hold it"
    assert read_learnings(path) == [FIRST, FENCED], "a reflection must round-trip exactly"

    for text in TEXTS:
        reflection = Reflection(12, "code/tests", text, ttl=3)
        write_learnings(path, [reflection])
        assert read_learnings(path) == [reflection], f"a reflection must round-trip exactly: {text!r}"
    everything = [Reflection(n, "code/tests", text) for n, text in enumerate(TEXTS, start=1)]
    write_learnings(path, everything)
    assert read_learnings(path) == everything, "a whole buffer must round-trip exactly, in order"
    write_learnings(path, [])
    assert path.read_text(encoding="utf-8") == HEADER and read_learnings(path) == [], "an empty buffer is just the header"

    path.write_text(
        "# Support bot learnings\n"
        "\n"
        "Reviewed by hand every Friday. An entry looks like this:\n"
        "\n"
        "```\n"
        "## support/billing (trial 1, ttl 5, failures 1)\n"
        "```\n"
        "\n"
        "## support/billing (trial 12, ttl 5, failures 3)\n"
        "\n"
        "\n"
        "```\n"
        "Quote the invoice number back before refunding.\n"
        "```\n"
        "Kept after the review on 2026-10-30.\n"
        "## support/refunds (trial 14, ttl 10, failures 1)\n"
        "```\n"
        "Check the refund window first.\n"
        "```",
        encoding="utf-8",
    )
    assert read_learnings(path) == [
        Reflection(12, "support/billing", "Quote the invoice number back before refunding.", 5, 3),
        Reflection(14, "support/refunds", "Check the refund window first.", 10, 1),
    ], "the header and the notes between entries are for people, not reflections"

    broken = [
        "## support/billing (trial 12, ttl 5, failure 3)\n\n```\nQuote the invoice number.\n```\n",
        "## support/billing (trial twelve, ttl 5, failures 3)\n\n```\nQuote the invoice number.\n```\n",
        "## Notes\n\nQuote the invoice number.\n",
        "## support/billing (trial 12, ttl 5, failures 3)\n\n## support/refunds (trial 14, ttl 10, failures 1)\n\n```\nCheck the window.\n```\n",
        "## support/billing (trial 12, ttl 5, failures 3)\n\n```\nQuote the invoice number.\n",
        "## support/billing (trial 12, ttl 5, failures 3)\n",
        "## support/billing (trial 0, ttl 5, failures 3)\n\n```\nQuote the invoice number.\n```\n",
        "## support/billing (trial 12, ttl 0, failures 3)\n\n```\nQuote the invoice number.\n```\n",
        "## support//billing (trial 12, ttl 5, failures 3)\n\n```\nQuote the invoice number.\n```\n",
        "## support/billing (trial 12, ttl 5, failures 3) checked\n\n```\nQuote the invoice number.\n```\n",
    ]
    for entry in broken:
        path.write_text(HEADER + "\n" + entry, encoding="utf-8")
        assert raises(ValueError, read_learnings, path), f"a broken entry is an error, not a silent skip: {entry!r}"

    write_learnings(path, [FENCED, FIRST])
    before = path.read_bytes()
    for bad in [
        Reflection(0, "math/arith/sum", "Start from nine."),
        Reflection(3, "math/arith/sum", "Start from nine.", ttl=0),
        Reflection(3, "math/arith/sum", "Start from nine.", failures=0),
        Reflection(3, "Math/Arith", "Start from nine."),
        Reflection(3, "math/arith/", "Start from nine."),
        Reflection(3, "math//arith", "Start from nine."),
        Reflection(3, "math arith", "Start from nine."),
        Reflection(3, "math/arith/sum", " \n\t"),
    ]:
        assert raises(ValueError, write_learnings, path, [FIRST, bad]), f"only what reads back is written: {bad}"
        assert path.read_bytes() == before, "a refused write leaves the file as it was"


def reflect(trial: Trial, verdict) -> str:
    """The fake Self-Reflector: a deterministic one-liner."""
    return f"{verdict.source} after {' -> '.join(trial.actions)}"


@pytest.mark.skip("Part 3")
def test_judge_and_trials() -> None:
    """The strongest signal available decides each trial, and only real lessons reach later trials."""
    long_run = tuple(f"step {i}" for i in range(51))
    cases = [
        (Trial(("edit", "test"), scalar=False, self_score=0.9), (False, "scalar")),
        (Trial(("test", "test"), scalar=True, self_score=0.1), (True, "scalar")),
        (Trial(long_run, scalar=True), (True, "scalar")),
        (Trial(("edit", "edit", "test"), self_score=0.95), (False, "stuck")),
        (Trial(("test", "edit", "test"), self_score=0.95), (True, "self")),
        (Trial(("search", "read", "read", "answer"), self_score=0.2), (False, "stuck")),
        (Trial(("read", "edit", "edit")), (False, "stuck")),
        (Trial(long_run, self_score=0.9), (False, "inefficient")),
        (Trial(long_run[:50], self_score=0.9), (True, "self")),
        (Trial(("search", "read") * 26, self_score=0.9), (False, "inefficient")),
        (Trial(("search", "search") + long_run, self_score=0.9), (False, "stuck")),
        (Trial(("search",), self_score=0.5), (True, "self")),
        (Trial(("search",), self_score=0.49), (False, "self")),
        (Trial(("search",), self_score=0.0), (False, "self")),
        (Trial(("search",), scalar=False, self_score=0.9, error="search API timed out"), (False, "external")),
        (Trial(("search", "search"), error="search API timed out"), (False, "external")),
        (Trial(("search",)), (False, "none")),
        (Trial(()), (False, "none")),
    ]
    for trial, expected in cases:
        verdict = judge(trial)
        assert (verdict.success, verdict.source) == expected, (
            f"scalar when available, self-evaluation when not, heuristics as safety rails: {trial}"
        )

    memory = EpisodicMemory()
    for reflection in (
        Reflection(2, "code/tests", "a", ttl=3),
        Reflection(5, "code/tests", "b", ttl=3),
        Reflection(9, "code/tests", "c", ttl=1),
    ):
        memory.add(reflection)
    assert {now: [r.text for r in memory.visible(now)] for now in range(1, 12)} == {
        1: [], 2: [], 3: ["a"], 4: ["a"], 5: ["a"], 6: ["b"], 7: ["b"], 8: ["b"], 9: [], 10: ["c"], 11: [],
    }, "a reflection from trial t with ttl n is seen by trials t+1 through t+n"

    memory = EpisodicMemory()
    memory.add(Reflection(3, "code/tests", "Run the failing test before editing."))
    memory.add(Reflection(11, "code/tests", "The fixture path is relative to the repo root.", ttl=2))
    script = {
        12: Trial(("read", "edit", "test"), scalar=False),
        13: Trial(("read", "test"), error="sandbox unreachable"),
        14: Trial(("edit", "edit"), self_score=0.9),
        15: Trial(("read", "edit", "test"), scalar=False, self_score=0.9),
        16: Trial(("read", "edit", "test"), scalar=True, self_score=0.2),
        17: Trial(("read",), scalar=True),
    }
    seen: dict[int, list[str]] = {}

    def act(n: int, reflections: list[Reflection]) -> Trial:
        seen[n] = [r.text for r in reflections]
        return script[n]

    verdicts = run_trials(act, reflect, memory, "code/tests", max_trials=6, start=12, ttl=2)
    assert [(v.success, v.source) for v in verdicts] == [
        (False, "scalar"),
        (False, "external"),
        (False, "stuck"),
        (False, "scalar"),
        (True, "scalar"),
    ], "one verdict per trial, saying which evaluator decided; a success ends the run"
    assert seen == {
        12: ["Run the failing test before editing.", "The fixture path is relative to the repo root."],
        13: ["Run the failing test before editing.", "The fixture path is relative to the repo root.",
             "scalar after read -> edit -> test"],
        14: ["scalar after read -> edit -> test"],
        15: ["stuck after edit -> edit"],
        16: ["stuck after edit -> edit", "scalar after read -> edit -> test"],
    }, "trial n sees what memory.visible(n) shows; an outage adds nothing"
    assert [(r.trial, r.text, r.ttl, r.failures) for r in memory.reflections()] == [
        (3, "Run the failing test before editing.", 10, 1),
        (11, "The fixture path is relative to the repo root.", 2, 1),
        (14, "stuck after edit -> edit", 2, 1),
        (15, "scalar after read -> edit -> test", 2, 2),
    ], "each lesson is stored with its trial and the run's ttl; a repeat refreshes it"
    assert {r.task_class for r in memory.reflections()} == {"code/tests"}, "each lesson is stored under the run's task class"

    asked: list[str] = []

    def spy(trial: Trial, verdict) -> str:
        asked.append(verdict.source)
        return reflect(trial, verdict)

    def always(trial: Trial):
        calls: list[int] = []

        def act(n: int, reflections: list[Reflection]) -> Trial:
            calls.append(n)
            if len(calls) > 10:
                raise AssertionError("each trial calls act once")
            return trial

        return act

    fresh = EpisodicMemory()
    verdicts = run_trials(always(Trial(("answer",), scalar=True)), spy, fresh, "qa/hotpotqa")
    assert ([(v.success, v.source) for v in verdicts], asked, len(fresh)) == ([(True, "scalar")], [], 0), (
        "a first-try success writes no reflection"
    )
    verdicts = run_trials(always(Trial(("search",), error="network down")), spy, fresh, "qa/hotpotqa", max_trials=3)
    assert ([v.source for v in verdicts], asked, len(fresh)) == (["external"] * 3, [], 0), (
        "every trial counts, and an outage is never reflected on"
    )
    verdicts = run_trials(always(Trial(("answer",))), spy, fresh, "qa/hotpotqa", max_trials=2)
    assert ([v.source for v in verdicts], asked, len(fresh)) == (["none", "none"], [], 0), (
        "without a signal there is nothing to reflect on"
    )

    strict = {1: Trial(("draft", "answer"), self_score=0.8), 2: Trial(("draft", "check", "answer"), self_score=0.95)}
    verdicts = run_trials(lambda n, rs: strict[n], spy, fresh, "qa/hotpotqa", max_trials=2, max_steps=2, pass_score=0.9)
    assert [(v.success, v.source) for v in verdicts] == [(False, "self"), (False, "inefficient")], (
        "the run judges with its own max_steps and pass_score"
    )


def run_async(coroutine, timeout: float = 5.0):
    """Run a coroutine, failing instead of hanging if it never finishes."""
    return asyncio.run(asyncio.wait_for(coroutine, timeout))


QUESTIONS = [
    "Which magazine was started first, Arthur's Magazine or First for Women?",
    "Were Scott Derrickson and Ed Wood of the same nationality?",
    'Who wrote the song "Hello, Goodbye"?',
    "What government position was held by the woman who portrayed Corliss Archer in the film Kiss and Tell?",
]
Q1, Q2, Q3, Q4 = QUESTIONS

# Each question's trials in order: how many event-loop turns the trial takes, and what it returns.
SCRIPT = {
    Q1: [
        (50, Trial(("search magazines", "answer"), scalar=False)),
        (30, Trial(("search magazines", "compare years", "answer"), scalar=True)),
    ],
    Q2: [(10, Trial(("search directors", "answer"), scalar=True))],
    Q3: [
        (30, Trial(("search song", "answer"), self_score=0.3)),
        (25, Trial(("search song",), error="search API timed out")),
        (35, Trial(("search song", "search song", "answer"), self_score=0.9)),
    ],
    Q4: [
        (20, Trial(("search film", "answer"))),
        (15, Trial(("search film", "search actress", "answer"), self_score=0.8)),
    ],
}


def scripted_attempts():
    """A fake model for every question: it records what each trial saw and when it finished."""
    seen: dict[tuple[str, int], list[str]] = {}
    finished: list[tuple[str, int]] = []

    async def attempt(task: str, n: int, reflections: list[Reflection]) -> Trial:
        if (task, n) in seen:
            raise AssertionError(f"each trial runs once: {task!r} trial {n}")
        seen[task, n] = [r.text for r in reflections]
        turns, trial = SCRIPT[task][n - 1]
        for _ in range(turns):
            await asyncio.sleep(0)
        finished.append((task, n))
        return trial

    return attempt, seen, finished


@pytest.mark.skip("Part 4")
def test_learning_curve() -> None:
    """Tasks run side by side, and each finished trial is a CSV row the moment it finishes."""
    attempt, seen, finished = scripted_attempts()

    async def run() -> list[tuple[int, str]]:
        curve = learning_curve(QUESTIONS, attempt, reflect, "qa/hotpotqa", ttl=1)
        return [(len(finished), chunk) async for chunk in curve]

    received = run_async(run())
    chunks = [chunk for _, chunk in received]
    rows = list(csv.reader(io.StringIO("".join(chunks), newline="")))
    assert len(rows) == len(chunks), "each string is exactly one CSV record"
    assert rows[0] == ["task", "trial", "success", "evaluator", "cumulative_success_rate"], "the header comes first"
    assert rows[1:] == [
        [Q2, "1", "1", "scalar", "0.2500"],
        [Q4, "1", "0", "none", "0.2500"],
        [Q3, "1", "0", "self", "0.2500"],
        [Q4, "2", "1", "self", "0.5000"],
        [Q1, "1", "0", "scalar", "0.5000"],
        [Q3, "2", "0", "external", "0.5000"],
        [Q1, "2", "1", "scalar", "0.7500"],
        [Q3, "3", "0", "stuck", "0.7500"],
    ], "one row per trial, in the order trials finish; the rate is the share of all tasks solved so far"
    assert [count for count, _ in received[1:]] == [1, 2, 3, 4, 5, 6, 7, 8], (
        "a row comes out as soon as its trial finishes"
    )
    assert seen == {
        (Q1, 1): [],
        (Q1, 2): ["scalar after search magazines -> answer"],
        (Q2, 1): [],
        (Q3, 1): [],
        (Q3, 2): ["self after search song -> answer"],
        (Q3, 3): [],
        (Q4, 1): [],
        (Q4, 2): [],
    }, "every task learns from its own trials only, through memory.visible"

    attempt, seen, finished = scripted_attempts()

    async def close_early() -> tuple[list[str], int, int]:
        curve = learning_curve(QUESTIONS, attempt, reflect, "qa/hotpotqa", ttl=1)
        first = [await curve.__anext__(), await curve.__anext__()]
        await curve.aclose()
        started = len(seen)
        for _ in range(200):
            await asyncio.sleep(0)
        return first, started, len(seen)

    first, started, later = run_async(close_early())
    assert next(csv.reader([first[1]]))[:2] == [Q2, "1"], "the first row is the first trial to finish"
    assert later == started, "closing the stream stops the tasks still running"

    async def instant(task: str, n: int, reflections: list[Reflection]) -> Trial:
        return Trial(("answer",), scalar=True)

    async def curve_of(tasks: list[str]) -> list[str]:
        return [chunk async for chunk in learning_curve(tasks, instant, reflect, "qa/hotpotqa")]

    assert list(csv.reader(io.StringIO("".join(run_async(curve_of([])))))) == [rows[0]], "no tasks, just the header"
    assert raises(ValueError, run_async, curve_of([Q2, Q2])), "a task name is a row key, so it must be unique"


CLASSES = [
    "math/arith/sum",
    "math/arith/product",
    "math/geometry",
    "code/test",
    "code/tests/flaky",
    "support/billing",
    "support/billing-disputes",
]


def lesson(task_class: str, trial: int, text: str, failures: int = 1) -> Reflection:
    return Reflection(trial, task_class, text, failures=failures)


@pytest.mark.skip("Part 5")
def test_scoped_recall() -> None:
    """A task class sees its own reflections and its ancestors', nearest first, within each cap."""
    tree = ScopeTree(CLASSES)
    attached = [
        lesson("math", 2, "Check the units before computing."),
        lesson("math", 5, "Write the formula down before the numbers.", failures=3),
        lesson("math/arith", 9, "Carry the remainder.", failures=2),
        lesson("math/arith/sum", 3, "Start from the largest number."),
        lesson("math/arith/sum", 7, "Stop raising a number at nine."),
        lesson("math/arith/sum", 7, "Raise the numbers from left to right.", failures=2),
        lesson("math/arith/sum", 4, "Pick larger values when the sum is short."),
        lesson("math/arith/product", 8, "Multiply by the larger factor first."),
        lesson("code", 1, "Read the whole traceback."),
        lesson("code/test", 6, "Run the single failing test."),
        lesson("code/tests", 10, "Pin the random seed.", failures=1),
        lesson("support/billing", 11, "Quote the invoice number back."),
        lesson("support/billing-disputes", 12, "Ask for the dispute id first."),
    ]
    for reflection in attached:
        tree.attach(reflection)

    def got(task_class: str, **caps) -> list[tuple[str, int, bool]]:
        return [(r.scope, r.reflection.trial, r.suspicious) for r in tree.recall(task_class, **caps)]

    assert got("math/arith/sum", per_level=2, total=4) == [
        ("math/arith/sum", 7, False),
        ("math/arith/sum", 7, False),
        ("math/arith", 9, False),
        ("math", 5, False),
    ], "nearest level first, at most per_level from each level and total in all"
    assert [r.reflection.text for r in tree.recall("math/arith/sum", per_level=2, total=4)][:2] == [
        "Stop raising a number at nine.",
        "Raise the numbers from left to right.",
    ], "within a level the newest trial first, ties in the order attached"
    assert got("math/arith/sum", per_level=3, total=6) == [
        ("math/arith/sum", 7, False),
        ("math/arith/sum", 7, False),
        ("math/arith/sum", 4, False),
        ("math/arith", 9, False),
        ("math", 5, False),
        ("math", 2, True),
    ], "a root reflection from a single failure is marked suspicious"
    assert got("math/geometry") == [("math", 5, False), ("math", 2, True)], "siblings never see each other"
    assert got("math") == [("math", 5, False), ("math", 2, True)], "a class does not see what is below it"
    assert got("code/tests/flaky") == [("code/tests", 10, False), ("code", 1, True)], (
        "ancestors are whole path segments: code/test is not above code/tests"
    )
    assert got("support/billing") == [("support/billing", 11, False)], "support/billing-disputes is a sibling"
    assert got("support/billing-disputes") == [("support/billing-disputes", 12, False)], "support/billing is a sibling"
    assert got("math/arith/sum", per_level=5, total=2) == [("math/arith/sum", 7, False), ("math/arith/sum", 7, False)], (
        "the total caps a single level too"
    )
    assert isinstance(tree.recall("math/arith/product")[0], Recalled), "recall returns Recalled entries"

    for unknown in ("math/arith/division", "Math/Arith", "math/", "physics"):
        assert raises(KeyError, tree.recall, unknown), f"an unknown task class is an error: {unknown!r}"
    assert raises(KeyError, tree.attach, lesson("math/algebra", 1, "Isolate the unknown.")), "attach to a known class"
    for bad in ("math//arith", "math/", "/math", "Math", "math arith", ""):
        assert raises(ValueError, ScopeTree, ["math/arith", bad]), f"a declared class must be a task-class path: {bad!r}"
