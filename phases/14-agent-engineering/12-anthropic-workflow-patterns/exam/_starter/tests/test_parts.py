import asyncio
import json
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from workflows.audit import AuditLog, Run
from workflows.bounds import Bounds, bounds
from workflows.dispatch import Ticket, route_stream
from workflows.orchestrator import PlanError, Result, Subtask, orchestrate
from workflows.patterns import (
    Refined,
    Round,
    Step,
    UnknownRoute,
    evaluator_optimizer,
    parallel_vote,
    prompt_chain,
    route,
)


def run(coro):
    return asyncio.run(coro)


def caught(error: type, call, *args):
    """The error that call(*args) raised, or None when it returned normally."""
    try:
        call(*args)
    except error as exc:
        return exc
    return None


def raises(error: type, call, *args) -> bool:
    return caught(error, call, *args) is not None


class Unscripted(Exception):
    """The workflow sent the model a prompt the test did not script."""


class Model:
    """A scripted stand-in for the LLM: one reply per prompt. It records every prompt it is sent."""

    def __init__(self, replies: dict[str, str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt not in self.replies:
            raise Unscripted(f"no reply scripted for {prompt!r}")
        return self.replies[prompt]


class Voters:
    """Scripted voters: call i answers answers[i] after delays[i] seconds.

    The answer is fixed when the call is made, so concurrent calls get the same answers whatever
    order they finish in. A cancelled call takes a few turns of the event loop to close its
    connection before it ends. The voters record the most calls they had in flight at once, how many
    are in flight now, and how many calls were cancelled.
    """

    def __init__(self, answers: list[str], delays: list[float]) -> None:
        self.answers = answers
        self.delays = delays
        self.calls = 0
        self.running = 0
        self.peak = 0
        self.cancelled = 0

    def __call__(self, prompt: str):
        i = self.calls
        self.calls += 1
        return self._reply(self.answers[i], self.delays[i])

    async def _reply(self, answer: str, delay: float) -> str:
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            for _ in range(3):
                await asyncio.sleep(0)
            self.cancelled += 1
            raise
        finally:
            self.running -= 1
        return answer


def classifier(model: Model):
    async def classify(text: str) -> str:
        return await model(LABEL.replace("{text}", text))

    return classify


def chain(model: Model, steps: list[tuple[str, str]]):
    """A route handler that runs a prompt chain and answers with its last output."""

    async def handle(text: str) -> str:
        return (await prompt_chain(text, model, steps))[-1].output

    return handle


LABEL = "Label this ticket as refund, bug or sales: {text}"
TICKET = "I want my money back for order A-981, it arrived broken"
EXTRACT = 'Pull the order out of this ticket. Reply in JSON like {"order": "A-123", "reason": "late"}.\nTicket: {text}'
ORDER = '{"order": "A-981", "reason": "arrived broken"}'
REPLY = "Write a short reply confirming this refund. Sign it {{agent_name}}; the CRM fills that in.\nOrder: {text}"
ANSWER = "Hi! Your refund for order A-981 is on its way."
BUG = "The export crashes when I save to my home folder"
REPRO = "List the steps that reproduce this bug: {text}"
STEPS = r"1. Export to C:\Users\ana\new.csv 2. The app closes"
TITLE = "Write a one-line issue title for these steps:\n{text}\nCopy any file path from the steps exactly: {text}"
ISSUE = r"Export to C:\Users\ana\new.csv closes the app"
TRIAGE = "Summarize this ticket for a person to pick up: {text}"
PRICING = "Do you offer volume pricing?"
MAYBE = "Not sure if I should return it or keep it"


@pytest.mark.skip("Part 1")
def test_patterns() -> None:
    """Chaining, routing, voting and evaluator-optimizer behave as their docstrings say."""
    model = Model(
        {
            LABEL.replace("{text}", TICKET): "Refund\n",
            EXTRACT.replace("{text}", TICKET): ORDER,
            REPLY.replace("{text}", ORDER): ANSWER,
            LABEL.replace("{text}", BUG): "\tBUG \n",
            REPRO.replace("{text}", BUG): STEPS,
            TITLE.replace("{text}", STEPS): ISSUE,
            LABEL.replace("{text}", PRICING): "Pricing",
            TRIAGE.replace("{text}", PRICING): "Asks about volume pricing.",
            LABEL.replace("{text}", MAYBE): "refund request",
            TRIAGE.replace("{text}", MAYBE): "Undecided between a return and keeping it.",
        }
    )
    handlers = {
        "refund": chain(model, [("extract", EXTRACT), ("reply", REPLY)]),
        "bug": chain(model, [("repro", REPRO), ("title", TITLE)]),
        "default": chain(model, [("triage", TRIAGE)]),
    }
    classify = classifier(model)
    assert run(route(TICKET, classify, handlers)) == ("refund", ANSWER), "the classifier's label picks the route"
    assert model.prompts == [
        LABEL.replace("{text}", TICKET),
        EXTRACT.replace("{text}", TICKET),
        REPLY.replace("{text}", ORDER),
    ], "each step of a chain gets the previous step's output"
    assert run(prompt_chain(TICKET, model, [("extract", EXTRACT), ("reply", REPLY)])) == [
        Step("extract", EXTRACT.replace("{text}", TICKET), ORDER),
        Step("reply", REPLY.replace("{text}", ORDER), ANSWER),
    ], "a chain returns one step per call"
    assert run(route(BUG, classify, handlers)) == ("bug", ISSUE), "every {text} gets the previous output, as it is"
    assert run(route(PRICING, classify, handlers)) == ("pricing", "Asks about volume pricing."), (
        "a label with no route goes to the default handler"
    )
    assert run(route(MAYBE, classify, handlers)) == ("refund request", "Undecided between a return and keeping it."), (
        "only an exact label picks a route"
    )
    without_default = {label: handler for label, handler in handlers.items() if label != "default"}
    error = caught(UnknownRoute, run, route(PRICING, classify, without_default))
    assert error is not None and "pricing" in str(error), (
        "with no default handler, an unknown label raises UnknownRoute naming it"
    )

    drafts = ["Refund sent.", ANSWER]
    asked: list = []

    async def propose(task: str, feedback):
        asked.append(feedback)
        return drafts[min(len(asked), len(drafts)) - 1]

    async def vague(task: str, feedback):
        asked.append(feedback)
        return "Refund sent."

    async def judge(task: str, candidate: str):
        return ("A-981" in candidate, "ok" if "A-981" in candidate else "name the order")

    refined = run(evaluator_optimizer("reply to the A-981 refund", propose, judge, max_iter=3))
    assert (refined, asked) == (
        Refined(ANSWER, [Round("Refund sent.", False, "name the order"), Round(ANSWER, True, "ok")]),
        [None, "name the order"],
    ), "the evaluator's feedback goes back to the proposer until a candidate passes"
    asked.clear()
    rejected = run(evaluator_optimizer("reply to the A-981 refund", vague, judge, max_iter=2))
    assert (rejected, asked) == (
        Refined(None, [Round("Refund sent.", False, "name the order")] * 2),
        [None, "name the order"],
    ), "a draft the evaluator rejected is never the answer"
    for too_few in (0, -1):
        empty = evaluator_optimizer("reply to the A-981 refund", vague, judge, max_iter=too_few)
        assert raises(ValueError, run, empty), "max_iter must be at least 1"

    question = "is this code safe to ship?"
    voters = Voters(["yes"] * 140 + ["no"] * 120 + ["unsure"] * 40, [0.006] * 300)
    start = time.perf_counter()
    outcome = run(parallel_vote(question, voters, n=300))
    elapsed = time.perf_counter() - start
    assert outcome == ("yes", Counter(yes=140, no=120, unsure=40)), (
        "with no majority, every vote is counted and the most common answer wins"
    )
    assert elapsed < 0.12, "the votes run concurrently"
    assert voters.peak == 300, "all the votes are in flight at once"
    stuck = Voters(["no", "yes", "no", "yes", "yes", "no", "yes"], [0.001, 0.007, 2.0, 0.008, 0.009, 2.0, 0.01])

    async def decide():
        start = time.perf_counter()
        outcome = await parallel_vote(question, stuck, n=7)
        elapsed = time.perf_counter() - start
        at_return = (stuck.running, stuck.cancelled)
        await asyncio.sleep(0.05)
        return outcome, elapsed, at_return, (stuck.running, stuck.cancelled)

    outcome, elapsed, at_return, later = run(decide())
    assert elapsed < 0.2, "a majority does not wait for the calls still running"
    assert outcome == ("yes", Counter(yes=4, no=1)), (
        "an answer wins once it has more than half the votes, with the votes back by then"
    )
    assert later == (0, 2), "the calls still running when the vote is decided are cancelled"
    assert at_return == later, "no call outlives the vote: parallel_vote returns after the cancelled calls end"
    tie = Voters(["yes", "no", "unsure", "yes", "no", "unsure"], [0.03, 0.02, 0.001, 0.03, 0.02, 0.001])
    assert run(parallel_vote(question, tie, n=6)) == ("yes", Counter(yes=2, no=2, unsure=2)), (
        "a tie goes to the answer asked for first, not the first one back"
    )
    split = Voters(["no", "yes", "yes", "no"], [0.25, 0.001, 0.002, 0.003])
    assert run(parallel_vote(question, split, n=4)) == ("no", Counter(no=2, yes=2)), (
        "half the votes is not a majority: without one, every reply is waited for, however slow"
    )


ROUTED = Run(
    run_id="run-0007",
    pattern="routing",
    steps=[
        Step("classify", "Label this ticket as refund, bug or sales: I want my money back", "Refund\n"),
        Step(
            "refund/extract",
            'Reply in JSON like {"order": "A-123"} & nothing else, <no prose>',
            '{"order": "A-981", "note": "arrived <broken> & late"}',
        ),
        Step("lookup", "order A-981", "\x1b[32mshipped\x1b[0m\x00"),
        Step("refund/reply", "Write the reply.", "  Hi Ana,\r\nyour refund for A-981 is on its way.\r\n\r\n"),
        Step("refund/reply", "", ""),
        Step("invoice", "page 1\x0cpage 2", " \n\t "),
        Step("explain", 'Explain: if a[b[0]]>1: print("<ok> & done")', 'It prints "<ok> & done" when a[b[0]]>1.'),
        Step("decode", "What do these codes mean?", r'"\x1b[0m" resets colour, "\u0000" is NUL; see C:\logs\new.txt'),
        Step("search", "grep -n --color=always x1b colors.py", '\x1b[32m3\x1b[0m:RESET = "\\x1b[0m"'),
        Step("export", "csv", "downloading 50%\rdownloading 100%"),
    ],
    branch="refund",
    output="  Hi Ana,\r\nyour refund for A-981 is on its way.\r\n\r\n",
)
REJECTED = Run(
    run_id="run-0008",
    pattern="evaluator-optimizer",
    steps=[
        Step("propose", "Reply to: where is my order?", "It shipped.\n"),
        Step("evaluate", "It shipped.\n", "FAIL: name the order & the date"),
        Step(
            "propose",
            "Reply to: where is my order?\nFix: name the order & the date",
            "  Zoë, order A-17 shipped on 3 May ✓  ",
        ),
        Step("evaluate", "  Zoë, order A-17 shipped on 3 May ✓  ", "FAIL: <date> is wrong"),
    ],
)
BLANK = Run(run_id="run_0009", pattern="routing", steps=[Step("classify", "???", "")], branch="", output="")
READABLE = [
    "routing",
    "evaluator-optimizer",
    "refund/extract",
    "Label this ticket as refund, bug or sales: I want my money back",
    'Reply in JSON like {"order": "A-123"} & nothing else, <no prose>',
    '{"order": "A-981", "note": "arrived <broken> & late"}',
    " \n\t ",
    "It shipped.\n",
    "Reply to: where is my order?\nFix: name the order & the date",
    "  Zoë, order A-17 shipped on 3 May ✓  ",
    "FAIL: <date> is wrong",
    'Explain: if a[b[0]]>1: print("<ok> & done")',
    r'"\x1b[0m" resets colour, "\u0000" is NUL; see C:\logs\new.txt',
]


def readable_text(path) -> list[str]:
    """What an auditor reads in a run document: every element's text and every attribute value."""
    root = ET.parse(path).getroot()
    assert root.tag == "run", "a run document's root element is <run>"
    return [value for node in root.iter() for value in (node.text, *node.attrib.values()) if value]


@pytest.mark.skip("Part 2")
def test_audit_record(tmp_path) -> None:
    """Each run is one XML document an auditor can read, and it reads back exactly."""
    folder = tmp_path / "audit"
    log = AuditLog(folder)
    paths = [log.write(record) for record in (ROUTED, REJECTED, BLANK)]
    assert [Path(p).resolve() for p in paths] == [
        (folder / f"{record.run_id}.xml").resolve() for record in (ROUTED, REJECTED, BLANK)
    ], "one document per run, named after its run id"
    reader = AuditLog(folder)
    assert reader.read("run-0007") == ROUTED, "every character of every step reads back, in order"
    assert reader.read("run-0008") == REJECTED, "a run with no branch and no output reads back with None"
    assert reader.read("run_0009") == BLANK, "an empty string reads back as an empty string, not None"
    seen = readable_text(paths[0]) + readable_text(paths[1])
    for value in READABLE:
        assert value in seen, f"text XML can hold is stored as it is, for auditors to read: {value!r}"
    assert raises(KeyError, reader.read, "run-0010"), "an unknown run id raises KeyError"
    for bad in ("../run-0007", "run 7", "", "run-0007.xml", "run-0007\n", "rün-7"):
        assert raises(ValueError, log.write, replace(ROUTED, run_id=bad)), f"not a run id: {bad!r}"
    assert sorted(p.name for p in folder.iterdir()) == ["run-0007.xml", "run-0008.xml", "run_0009.xml"]


class Planner:
    """A scripted orchestrator: reply i is its plan for round i. It records the results it is shown."""

    def __init__(self, *plans) -> None:
        self.plans = [plan if isinstance(plan, str) else json.dumps(plan) for plan in plans]
        self.shown: list[list[Result]] = []

    async def __call__(self, task: str, results) -> str:
        assert len(self.shown) < len(self.plans), (
            "the orchestrator was asked for a plan after the run should have stopped"
        )
        self.shown.append(list(results))
        return self.plans[len(self.shown) - 1]


class Crew:
    """Scripted workers. Each subtask takes its own time; the crew records every call it gets and the
    most subtasks it had running at once."""

    def __init__(self, names, seconds: dict[tuple[str, str], float] = {}) -> None:
        self.seconds = seconds
        self.calls: list[Subtask] = []
        self.running = 0
        self.peak = 0
        self.workers = {name: self._worker(name) for name in names}

    def _worker(self, name: str):
        async def work(task: str) -> str:
            self.calls.append(Subtask(name, task))
            self.running += 1
            self.peak = max(self.peak, self.running)
            try:
                await asyncio.sleep(self.seconds.get((name, task), 0.001))
            finally:
                self.running -= 1
            return f"{name} on {task}: ok"

        return work


class Synthesizer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Result]]] = []

    async def __call__(self, task: str, results) -> str:
        self.calls.append((task, list(results)))
        return " | ".join(result.output for result in results)


def ask(*pairs) -> list[dict]:
    return [{"worker": worker, "task": task} for worker, task in pairs]


SQL = ("security", "check the diff for SQL injection")
ERRORS = ("python", "review error handling")
SEC_ERRORS = ("security", "review error handling")
NAMES = ("python", "review naming")
LENGTH = ("style", "check line length")
DOCS = ("docs", "check the docstrings")
AUTH = ("security", "check the new endpoint for auth")
CREW = ("python", "security", "style", "docs")


def done_by(pairs_and_rounds) -> list[Result]:
    return [Result(Subtask(*pair), f"{pair[0]} on {pair[1]}: ok", number) for pair, number in pairs_and_rounds]


@pytest.mark.skip("Part 3")
def test_orchestrator() -> None:
    """The orchestrator decides which workers run; the run is bounded and the synthesis keeps its order."""
    crew = Crew(
        CREW,
        {SQL: 0.04, ERRORS: 0.01, SEC_ERRORS: 0.03, NAMES: 0.02, DOCS: 0.03, AUTH: 0.01, LENGTH: 0.02},
    )
    planner = Planner(
        {"subtasks": ask(SQL, ERRORS, SQL, SEC_ERRORS, NAMES, LENGTH, DOCS), "done": False},
        {"subtasks": ask(ERRORS, SQL, DOCS, AUTH, LENGTH, ERRORS), "done": True},
    )
    synthesize = Synthesizer()
    outcome = run(orchestrate("review PR 812", planner, crew.workers, synthesize, max_subtasks=4, max_rounds=2))
    expected = done_by([(SQL, 1), (ERRORS, 1), (SEC_ERRORS, 1), (NAMES, 1), (DOCS, 2), (AUTH, 2), (LENGTH, 2)])
    assert outcome.results == expected, "results keep the order the orchestrator asked for them in"
    assert Counter(crew.calls) == Counter(result.subtask for result in expected), (
        "each subtask runs once: a repeat, or a subtask from an earlier round, is not run again"
    )
    assert outcome.dropped == [Subtask(*LENGTH), Subtask(*DOCS)], (
        "subtasks past the round's limit are dropped and recorded"
    )
    assert crew.peak == 4, "a round's subtasks run at the same time"
    assert (outcome.rounds, outcome.stopped) == (2, "done"), "a plan that says done is the last one"
    assert planner.shown == [[], expected[:4]], "each round the orchestrator sees the results so far"
    assert synthesize.calls == [("review PR 812", expected)], "every result is synthesized once, in order"
    assert outcome.output == " | ".join(result.output for result in expected)

    endless = Planner(*({"subtasks": ask(("python", f"review module {i}")), "done": False} for i in range(1, 4)))
    outcome = run(orchestrate("review PR 813", endless, Crew(CREW).workers, Synthesizer(), max_rounds=3))
    assert (outcome.rounds, outcome.stopped, len(outcome.results)) == (3, "max_rounds", 3), (
        "the orchestrator does not loop indefinitely"
    )
    assert endless.shown == [outcome.results[:n] for n in range(3)], "each round the orchestrator sees every result so far"
    again = Planner(
        {"subtasks": ask(NAMES), "done": False},
        {"subtasks": ask(NAMES), "done": False},
        {"subtasks": ask(DOCS), "done": True},
    )
    outcome = run(orchestrate("review PR 817", again, Crew(CREW).workers, Synthesizer()))
    assert ([result.subtask for result in outcome.results], outcome.rounds) == ([Subtask(*NAMES), Subtask(*DOCS)], 3), (
        "a round with nothing new to run does not end the run"
    )
    synthesize = Synthesizer()
    nothing = Planner({"subtasks": [], "done": True})
    outcome = run(orchestrate("review PR 814", nothing, Crew(CREW).workers, synthesize))
    assert (outcome.results, outcome.rounds, outcome.stopped, synthesize.calls) == (
        [],
        1,
        "done",
        [("review PR 814", [])],
    ), "an orchestrator can decide no worker is needed"

    crew = Crew(CREW)
    unknown = {"subtasks": ask(NAMES, ("translator", "translate the docstrings")), "done": True}
    error = caught(PlanError, run, orchestrate("review PR 815", Planner(unknown), crew.workers, Synthesizer()))
    assert error is not None and "translator" in str(error), "a subtask for an unknown worker is a PlanError naming it"
    assert crew.calls == [], "a bad plan raises before any of its subtasks start"
    one_slot = orchestrate("review PR 815", Planner(unknown), crew.workers, Synthesizer(), max_subtasks=1)
    assert raises(PlanError, run, one_slot), "the whole plan is checked, including subtasks past the round's limit"
    for reply in (
        "Sure! First the python reviewer should look at error handling.",
        '["python", "security"]',
        '{"subtasks": [{"worker": "python"}], "done": false}',
        '{"subtasks": {"worker": "python", "task": "review naming"}, "done": false}',
        '{"subtasks": [], "done": "false"}',
        '{"subtasks": []}',
    ):
        one_round = orchestrate("review PR 816", Planner(reply), crew.workers, Synthesizer(), max_rounds=1)
        assert raises(PlanError, run, one_round), f"a reply that is not a plan raises PlanError: {reply}"


# id, ticket text, the classifier's raw label, seconds in its handler
INBOX = [
    ("t1", 'My mug arrived broken.\nOrder "A-17", from Zoë', "Refund\n", 0.06),
    ("t2", "Refund order A-18 please", " refund", 0.06),
    ("t3", "I was charged twice", "REFUND", 0.06),
    ("t4", "The CLI crashes on ctrl-c", "bug", 0.04),
    ("t5", "Do you offer volume pricing?", "Sales", 0.02),
    ("t6", "What is your favourite colour?", "chitchat", 0.0),
    ("t7", "Export to CSV drops rows", "Bug\n", 0.085),
    ("t8", "Can I get a quote for 40 seats?", "sales", 0.15),
]
LABELS = {text: label for _, text, label, _ in INBOX}
SECONDS = {text: seconds for _, text, _, seconds in INBOX}
QUEUE = [Ticket(ticket_id, text) for ticket_id, text, _, _ in INBOX]
LIMITS = {"refund": 1, "bug": 2, "sales": 3}


async def label_of(text: str) -> str:
    await asyncio.sleep(0)
    return LABELS[text]


class Labeler:
    """A scripted classifier like label_of that takes a millisecond per ticket. It records the most
    tickets it was classifying at once."""

    def __init__(self) -> None:
        self.running = 0
        self.peak = 0

    async def __call__(self, text: str) -> str:
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(0.001)
        finally:
            self.running -= 1
        return LABELS[text]


class Desk:
    """Scripted route handlers. Each ticket text takes its own time in its handler; the desk records
    the most tickets each route had in its handler at once, and which tickets it finished."""

    def __init__(self, seconds: dict[str, float] = {}, failures: dict[str, Exception] = {}) -> None:
        self.seconds = seconds
        self.failures = failures
        self.active: Counter = Counter()
        self.peak: Counter = Counter()
        self.finished: list[str] = []
        self.handlers = {route: self._handler(route) for route in LIMITS}

    def _handler(self, route: str):
        async def handle(text: str) -> str:
            self.active[route] += 1
            self.peak[route] = max(self.peak[route], self.active[route])
            try:
                await asyncio.sleep(self.seconds.get(text, 0.0))
            finally:
                self.active[route] -= 1
            if text in self.failures:
                raise self.failures[text]
            self.finished.append(text)
            return f"{route} desk: {text}"

        return handle


async def arriving(tickets: list[Ticket], gap: float = 0.0, pulled: list | None = None):
    for ticket in tickets:
        if pulled is not None:
            pulled.append(ticket.id)
        yield ticket
        await asyncio.sleep(gap)


def records(lines: list[str]) -> list[dict]:
    """Parse the stream the way an NDJSON client would: one JSON object per line."""
    text = "".join(lines)
    assert not text or text.endswith("\n"), "every line ends with a line break"
    return [json.loads(line) for line in text.split("\n")[:-1]]


FINISHED = [
    {"ticket": "t6", "route": "chitchat", "error": "unknown route"},
    {"ticket": "t5", "route": "sales", "output": "sales desk: Do you offer volume pricing?"},
    {"ticket": "t4", "route": "bug", "output": "bug desk: The CLI crashes on ctrl-c"},
    {"ticket": "t1", "route": "refund", "output": 'refund desk: My mug arrived broken.\nOrder "A-17", from Zoë'},
    {"ticket": "t7", "route": "bug", "error": "RuntimeError: issue tracker is down"},
    {"ticket": "t2", "route": "refund", "output": "refund desk: Refund order A-18 please"},
    {"ticket": "t8", "route": "sales", "output": "sales desk: Can I get a quote for 40 seats?"},
    {"ticket": "t3", "route": "refund", "output": "refund desk: I was charged twice"},
]


@pytest.mark.skip("Part 4")
def test_route_stream() -> None:
    """Tickets are routed as they arrive, each route within its limit, and lines come out as tickets finish."""
    desk = Desk(SECONDS, {"Export to CSV drops rows": RuntimeError("issue tracker is down")})

    async def drain(stream) -> list[str]:
        return [line async for line in stream]

    labeler = Labeler()
    lines = run(drain(route_stream(arriving(QUEUE), labeler, desk.handlers, LIMITS)))
    got = records(lines)
    without_ms = [{key: value for key, value in record.items() if key != "ms"} for record in got]
    assert sorted(without_ms, key=lambda r: r["ticket"]) == sorted(FINISHED, key=lambda r: r["ticket"]), (
        "one line per ticket: an output, or an error for an unknown route or a failed handler"
    )
    assert desk.peak == Counter(refund=1, bug=2, sales=2), "a route has at most its limit of tickets in its handler"
    assert without_ms == FINISHED, "lines come out in the order the tickets finish"
    assert all(type(record.get("ms")) in (int, float) for record in got), "every line has ms, a number"
    assert got[-1]["ms"] >= 170, "ms counts from the ticket's arrival, including its wait for the route"
    assert labeler.peak > 1, "each ticket is classified as soon as it arrives, not after the one before it"

    async def congested() -> tuple[float, int, int]:
        refund = "Refund order A-18 please"
        desk = Desk({refund: 0.06})
        queue = [Ticket(f"r{i}", refund) for i in range(10)]
        stream = route_stream(arriving([*queue, Ticket("s1", PRICING)]), label_of, desk.handlers, LIMITS)
        start = time.perf_counter()
        async for line in stream:
            if json.loads(line)["ticket"] == "s1":
                break
        elapsed = time.perf_counter() - start
        await stream.aclose()
        refunds_at_close = desk.finished.count(refund)
        await asyncio.sleep(0.08)
        return elapsed, refunds_at_close, desk.finished.count(refund)

    elapsed, at_close, later = run(congested())
    assert elapsed < 0.05, "a busy route does not hold up tickets for other routes"
    assert (at_close, later) == (0, 0), "closing the stream cancels the tickets still in flight"

    async def first_lines() -> tuple[str, int, list[str], int, int]:
        pulled: list[str] = []
        arrivals = arriving([Ticket(f"c{i}", PRICING) for i in range(10)], gap=0.03, pulled=pulled)
        stream = route_stream(arrivals, label_of, Desk().handlers, LIMITS)
        first = await stream.__anext__()
        count = len(pulled)
        rest = [await stream.__anext__() for _ in range(4)]
        await stream.aclose()
        at_close = len(pulled)
        await asyncio.sleep(0.1)
        return first, count, rest, at_close, len(pulled)

    first, count, rest, at_close, later = run(first_lines())
    assert records([first])[0]["ticket"] == "c0" and count <= 2, "a line is sent as soon as its ticket is done"
    assert all(record["ms"] < 50 for record in records([first, *rest])), (
        "ms counts from the ticket's arrival, not from the start of the stream"
    )
    assert later == at_close, "closing the stream stops pulling tickets"


def llm(ms: int) -> dict:
    return {"type": "llm", "ms": ms}


def tool(ms: int) -> dict:
    return {"type": "tool", "ms": ms}


REFUND_FLOW = {
    "type": "chain",
    "steps": [
        llm(800),
        tool(150),
        {"type": "evaluator-optimizer", "max_iter": 4, "propose": llm(900), "evaluate": llm(400)},
    ],
}
BUG_FLOW = {
    "type": "parallel",
    "sections": [
        llm(1200),
        {"type": "chain", "steps": [tool(2500), llm(600)]},
        {"type": "parallel", "n": 5, "node": llm(700)},
    ],
}
SALES_FLOW = {
    "type": "orchestrator",
    "max_rounds": 2,
    "max_subtasks": 4,
    "planner": llm(500),
    "workers": {
        "pricing": {"type": "evaluator-optimizer", "max_iter": 2, "propose": llm(400), "evaluate": llm(200)},
        "legal": {"type": "chain", "steps": [tool(1500), llm(300)]},
        "crm": llm(100),
    },
    "synthesizer": llm(700),
}
DESK_FLOW = {
    "type": "route",
    "classifier": llm(300),
    "branches": {"refund": REFUND_FLOW, "bug": BUG_FLOW, "sales": SALES_FLOW, "spam": tool(20)},
}


@pytest.mark.skip("Part 5")
def test_cost_bounds() -> None:
    """A nested workflow spec has exact bounds on its LLM calls and its worst-case latency."""
    assert (bounds(llm(300)), bounds(tool(20))) == (Bounds(1, 1, 300), Bounds(0, 0, 20)), (
        "a tool call is not an LLM call"
    )
    assert bounds(REFUND_FLOW) == Bounds(3, 9, 6150), (
        "a chain adds up; an evaluator-optimizer runs 1 to max_iter rounds"
    )
    assert bounds(BUG_FLOW) == Bounds(7, 7, 3100), (
        "parallel calls add up, but the wait is only as long as the slowest"
    )
    assert bounds(SALES_FLOW) == Bounds(2, 35, 5300), (
        "an orchestrator can stop after one plan, or use every round and every worker slot"
    )
    assert bounds(DESK_FLOW) == Bounds(1, 36, 6450), (
        "a route pays for its classifier and then for one branch, whichever is cheapest, costliest or slowest"
    )
    voted = {
        "type": "parallel",
        "n": 3,
        "node": {
            "type": "route",
            "classifier": tool(5),
            "branches": {"short": llm(100), "long": {"type": "chain", "steps": [llm(50), llm(70)]}},
        },
    }
    assert bounds(voted) == Bounds(3, 6, 125), "n copies of one node run at the same time"
    open_ended = {"type": "route", "classifier": llm(50), "branches": {"open": {"type": "agent", "max_turns": 40}}}
    agentic = {"type": "chain", "steps": [llm(100), open_ended]}
    error = caught(ValueError, bounds, agentic)
    assert error is not None and "agent" in str(error), "an unknown node type raises ValueError naming it"
    for broken in (
        {"type": "parallel", "n": 0, "node": llm(10)},
        {"type": "evaluator-optimizer", "max_iter": 0, "propose": llm(10), "evaluate": llm(10)},
        {**SALES_FLOW, "max_rounds": 0},
        {**SALES_FLOW, "max_subtasks": 0},
        {"type": "evaluator-optimizer", "max_iter": -1, "propose": llm(10), "evaluate": llm(10)},
    ):
        assert raises(ValueError, bounds, broken), f"counts must be at least 1: {broken}"
