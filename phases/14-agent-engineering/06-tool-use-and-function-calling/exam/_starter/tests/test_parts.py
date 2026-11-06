import asyncio
import copy
import dataclasses
import datetime
import dbm
import json
import threading
import time

import pytest
from toolcall.cases import Call, Case, CaseBank
from toolcall.chains import ChainError, Ran, Step, run_chain
from toolcall.drive import TOOLS as DRIVE_TOOLS
from toolcall.drive import FakeDrive
from toolcall.pipeline import run_suite
from toolcall.registry import ToolCall, ToolDef, ToolRegistry, ToolResult
from toolcall.scoring import Verdict, grade, score_run, summarize
from toolcall.service import EvalService


def within(coro, seconds: float = 3.0):
    """Run a coroutine, failing with TimeoutError instead of hanging."""
    return asyncio.run(asyncio.wait_for(coro, seconds))


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return within(drain())


def typed(value):
    """value with every scalar tagged by its type, so 5, 5.0 and "5" stay apart."""
    if dataclasses.is_dataclass(value):
        fields = dataclasses.fields(value)
        return type(value).__name__, {f.name: typed(getattr(value, f.name)) for f in fields}
    if isinstance(value, dict):
        return {key: typed(item) for key, item in value.items()}
    if isinstance(value, list):
        return [typed(item) for item in value]
    return type(value).__name__, value


THERMOSTAT = {
    "type": "object",
    "properties": {
        "room": {"type": "string", "enum": ["lab", "office", "kitchen"]},
        "celsius": {"type": "number", "minimum": 5, "maximum": 30},
        "offset": {"type": "number"},
    },
    "required": ["room", "celsius"],
}
BOOKING = {
    "type": "object",
    "properties": {
        "room": {"type": "string"},
        "people": {"type": "integer", "minimum": 1, "maximum": 12},
        "date": {"type": "string", "format": "date"},
        "floor": {"type": "integer"},
    },
    "required": ["room", "people", "date"],
}
QUERY = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def set_thermostat(room: str, celsius: float, offset: float = 0.0) -> str:
    return f"{room} set to {round((celsius + offset) * 2) / 2} C"


def book_room(room: str, people: int, date: str, floor: int = 0) -> str:
    day = WEEKDAYS[datetime.date.fromisoformat(date).weekday()]
    return f"{room} on floor {floor} booked for {people} on {day} {date}"


@pytest.mark.skip("Part 1")
def test_registry_dispatch() -> None:
    """Arguments are checked the way the lesson asks, and a stuck tool cannot stall the agent."""
    reg = ToolRegistry()
    reg.register(ToolDef("set_thermostat", "Set a room's target temperature.", THERMOSTAT,
                         set_thermostat))
    reg.register(ToolDef("book_room", "Book a meeting room for a group on one day.", BOOKING,
                         book_room))

    def thermostat(arguments: str) -> ToolResult:  # the model's arguments arrive as JSON text
        return reg.dispatch(ToolCall("t1", "set_thermostat", json.loads(arguments)))

    def book(**args) -> ToolResult:
        return reg.dispatch(ToolCall("b1", "book_room", {"room": "Ada", "date": "2026-03-02", **args}))

    stray = thermostat('{"room": "lab", "celsius": NaN}')
    assert (stray.tool_use_id, stray.ok) == ("t1", False) and stray.content.startswith(
        "validation error: celsius"
    ), "a number must be finite before the tool runs"
    for raw in ("NaN", '"nan"', "Infinity", '"-Infinity"', "1e999", '"1e999"'):
        result = thermostat('{"room": "lab", "celsius": 21, "offset": %s}' % raw)
        assert result.content.startswith("validation error: offset"), (
            f"a number must be finite before the tool runs, offset {raw}"
        )
    assert thermostat('{"room": "lab", "celsius": "21.5", "offset": -0.2}') == ToolResult(
        "t1", True, "lab set to 21.5 C"
    ), "a number written as a string is still a number"

    for raw in (" 7", "7 ", "+7", "1_000", "٣", "1٣", "07", "7\n", "7.0", "1e1"):
        assert book(people=4, floor=raw).content.startswith("validation error: floor"), (
            f"only a canonical decimal string becomes an integer, not {raw!r}"
        )
    assert book(people="5", floor="-1") == ToolResult(
        "b1", True, "Ada on floor -1 booked for 5 on Monday 2026-03-02"
    ), "a canonical decimal string is coerced"
    for raw in (" 2.5", "2.5 ", "2_5", "٢.٥", "2.٥", "+2.5", "02.5", ".5", "2."):
        result = thermostat('{"room": "lab", "celsius": 21, "offset": %s}' % json.dumps(raw))
        assert result.content.startswith("validation error: offset"), (
            f"only a string written as a JSON number becomes a number, not {raw!r}"
        )
    assert thermostat('{"room": "lab", "celsius": "2.15e1", "offset": "-0.2"}').content == (
        "lab set to 21.5 C"
    ), "a JSON number in a string is coerced"

    for bad in ("2026-02-30", "2026-02-29", "2026-13-01", "2026-2-5", "20260302", "2026-W10-1",
                "2026-03-02T09:00", "2026-03-02 "):
        assert book(people=4, date=bad).content.startswith("validation error: date"), (
            f"a date must exist and be written YYYY-MM-DD, not {bad!r}"
        )
    assert book(people=4, date="2028-02-29").content == (
        "Ada on floor 0 booked for 4 on Tuesday 2028-02-29"
    ), "a leap day is a real date"

    release = threading.Event()

    def search_archive(query: str) -> str:
        release.wait(2.5)  # a backend that hangs
        return f"archived results for {query}"

    def lookup(query: str) -> str:
        time.sleep(0.05)
        return f"found {query}"

    def flaky(query: str) -> str:
        raise ConnectionError("archive offline")

    reg.register(ToolDef("search_archive", "Search the cold archive.", QUERY, search_archive,
                         timeout_s=0.01))
    reg.register(ToolDef("lookup", "Look a term up in the glossary.", QUERY, lookup, timeout_s=2.0))
    reg.register(ToolDef("flaky", "Search the warm archive.", QUERY, flaky, timeout_s=2.0))
    try:
        start = time.perf_counter()
        stuck = reg.dispatch(ToolCall("s1", "search_archive", {"query": "q3 board deck"}))
        elapsed = time.perf_counter() - start
        assert (stuck.tool_use_id, stuck.ok) == ("s1", False) and stuck.content.startswith(
            "timeout: search_archive"
        ), "a tool that overruns its timeout_s gets a timeout observation"
        assert elapsed < 0.25, "dispatch stops waiting once timeout_s has passed"
        assert reg.dispatch(ToolCall("s2", "lookup", {"query": "q3"})) == ToolResult(
            "s2", True, "found q3"
        ), "a tool within its own timeout_s still answers while a stuck call runs on"
        assert reg.dispatch(ToolCall("s3", "flaky", {"query": "q3"})) == ToolResult(
            "s3", False, "execution error: ConnectionError: archive offline"
        ), "an executor that raises is still an execution error"
    finally:
        release.set()


def drive_tools(*names: str) -> list[dict]:
    return [tool for tool in DRIVE_TOOLS if tool["name"] in names]


WEATHER = {
    "name": "get_weather",
    "description": "Current weather for one city. Use it for any question about the weather now.",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"},
        },
        "required": ["city"],
    },
}
FORECAST = {
    "name": "get_forecast",
    "description": "Tomorrow's forecast for one city. Use it only for questions about tomorrow.",
    "input_schema": WEATHER["input_schema"],
}
BOOK = {
    "name": "book_room",
    "description": "Book a meeting room for a group on one day.",
    "input_schema": {
        "type": "object",
        "properties": {
            "room": {"type": "string"},
            "people": {"type": "integer", "minimum": 1, "maximum": 12},
            "date": {"type": "string", "format": "date"},
            "budget": {"type": "number"},
            "code": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["room", "people", "date"],
    },
}
Q1 = "Q1 revenue: 1.2M"
RENAME_TOOLS = drive_tools("list_files", "read_file", "write_file", "move_file", "delete_file")
RENAME_START = {"files": {"reports/q1.txt": Q1, "notes.txt": "call Ana"}}
RENAME_DONE = {"files": {"reports/q1-final.txt": Q1}}
MOVE = Call("move_file", {"src": "reports/q1.txt", "dst": "reports/q1-final.txt"})
DELETE_NOTES = Call("delete_file", {"path": "notes.txt"})


def drive_state() -> dict:
    return {
        "files": {
            "reports/q1.txt": Q1,
            "reports/q2.txt": "draft\nQ2 revenue: ?",
            "reports/q3.txt": "Q3 numbers, draft 2",
            "notes.txt": "call Ana",
        }
    }


CASES = [
    Case(
        "weather/zürich 3",
        "live",
        ["Wie warm ist es gerade in Zürich? Bitte in Fahrenheit."],
        [WEATHER, FORECAST],
        [
            [Call("get_weather", {"city": "Zürich", "unit": "fahrenheit"})],
            [Call("get_weather", {"city": "Zurich", "unit": "fahrenheit"})],
        ],
    ),
    Case(
        "weather/two cities",
        "live",
        ["Is it warmer in Lisbon or in Oslo right now?"],
        [WEATHER, BOOK],
        [[Call("get_weather", {"city": "Lisbon"}), Call("get_weather", {"city": "Oslo"})]],
    ),
    Case(
        "book/ada 1",
        "non_live",
        ["Book Ada for 4 people on 2 March 2026. Budget 200, cost code 5."],
        [BOOK, WEATHER],
        [
            [Call("book_room", {"room": "Ada", "people": 4, "date": "2026-03-02",
                                "budget": 200, "code": "5"})],
            [Call("book_room", {"room": "Ada Lovelace", "people": 4, "date": "2026-03-02",
                                "budget": 200.0, "code": "5"})],
        ],
    ),
    Case(
        "rename_report",
        "live",
        ["Rename reports/q1.txt to reports/q1-final.txt, then delete notes.txt."],
        RENAME_TOOLS,
        [[MOVE, DELETE_NOTES]],
        RENAME_START,
        RENAME_DONE,
    ),
    Case(
        "rename report",
        "multi_turn",
        ["Rename reports/q1.txt to reports/q1-final.txt.", "Thanks. Now delete notes.txt."],
        RENAME_TOOLS,
        [[MOVE, DELETE_NOTES]],
        RENAME_START,
        RENAME_DONE,
    ),
    Case(
        "clean up/2",
        "agentic",
        ["Move every report that mentions 'draft' into archive/."],
        drive_tools("list_files", "search_files", "read_file", "move_file"),
        [],
        drive_state(),
        {
            "files": {
                "reports/q1.txt": Q1,
                "archive/q2.txt": "draft\nQ2 revenue: ?",
                "archive/q3.txt": "Q3 numbers, draft 2",
                "notes.txt": "call Ana",
            }
        },
    ),
    Case("no tool/1", "hallucination", ["What is the capital of Australia?"], [WEATHER, BOOK]),
]
IDS = sorted(case.case_id for case in CASES)


@pytest.mark.skip("Part 2")
def test_case_bank(tmp_path) -> None:
    """Cases survive a round trip through the dbm file exactly, types and order included."""
    path = str(tmp_path / "cases")
    pristine = copy.deepcopy(CASES)
    bank = CaseBank(path)
    for case in CASES:
        bank.add(case)
    assert typed(bank.get("book/ada 1")) == typed(pristine[2]), (
        "a case comes back exactly, value types included"
    )
    assert typed(CASES) == typed(pristine), "add does not change the caller's case"
    bank.close()

    reopened = CaseBank(path)
    assert reopened.ids() == IDS, "a reopened bank lists every id exactly, sorted"
    assert [typed(reopened.get(case.case_id)) for case in pristine] == typed(pristine), (
        "every case comes back exactly after a reopen"
    )
    assert reopened.ids("live") == ["rename_report", "weather/two cities", "weather/zürich 3"], (
        "ids can be listed for one category"
    )
    assert typed(reopened.cases("multi_turn")) == typed([pristine[4]]), "cases by category"
    assert [case.case_id for case in reopened.cases()] == IDS, "cases come in id order"
    with pytest.raises(KeyError):
        reopened.get("weather/oslo 1")
    with pytest.raises(ValueError):
        reopened.add(CASES[2])
    assert typed(reopened.get("book/ada 1")) == typed(pristine[2]), (
        "a stored case is never replaced"
    )

    zurich, book, rename, clean_up, no_tool = CASES[0], CASES[2], CASES[4], CASES[5], CASES[6]
    room = {"room": "Ada", "people": 4, "date": "2026-03-02"}

    def rejected(case: Case) -> bool:
        try:
            reopened.add(case)
        except ValueError:
            return True
        return False

    variant = dataclasses.replace
    for why, case in (
        ("id holds a '#'", variant(book, case_id="book/ada #2")),
        ("id holds a line break", variant(book, case_id="book/ada\n2")),
        ("id is empty", variant(book, case_id="")),
        ("category is unknown", variant(book, case_id="x1", category="relevance")),
        ("answer calls a tool the catalog lacks",
         variant(book, case_id="x2", accepted=[[Call("book_rooms", room)]])),
        ("answer breaks its tool's schema",
         variant(book, case_id="x3", accepted=[[Call("book_room", {**room, "people": 40})]])),
        ("answer has a date that does not exist",
         variant(book, case_id="x4", accepted=[[Call("book_room", {**room, "date": "2026-02-30"})]])),
        ("non_live case has no answers", variant(book, case_id="x5", accepted=[])),
        ("answer is empty", variant(book, case_id="x6", accepted=[[]])),
        ("hallucination case has answers",
         variant(no_tool, case_id="x7", accepted=[[Call("get_weather", {"city": "Canberra"})]])),
        ("multi_turn case has no expected state", variant(rename, case_id="x8", expected_state=None)),
        ("multi_turn case has no initial state", variant(rename, case_id="x9", initial_state=None)),
        ("live case has no answers", variant(zurich, case_id="x10", accepted=[])),
        ("agentic case has no initial state", variant(clean_up, case_id="x11", initial_state=None)),
        ("second answer breaks its tool's schema",
         variant(book, case_id="x12",
                 accepted=[book.accepted[0], [Call("book_room", {**room, "people": 40})]])),
    ):
        assert rejected(case), f"add rejects a case whose {why}"
    assert reopened.ids() == IDS, "a rejected case is not stored"
    reopened.close()

    def is_json(value: bytes) -> bool:
        try:
            return isinstance(json.loads(value), dict)
        except ValueError:
            return False

    with dbm.open(path, "r") as raw:
        keys = list(raw.keys())
        assert len(keys) == len(CASES), "one dbm key per case"
        assert all(is_json(raw[key]) for key in keys), "each value is JSON"


def weather(**args) -> Call:
    return Call("get_weather", args)


def booking(**args) -> Call:
    return Call("book_room", {"room": "Ada", "people": 4, "date": "2026-03-02", "code": "5", **args})


@pytest.mark.skip("Part 3")
def test_bfcl_scoring() -> None:
    """AST matching, state-based checks and hallucination, weighted 40/30/10/10/10."""
    zurich, two, book, rename_live, rename_turns, clean_up, no_tool = CASES
    untouched = typed(CASES)

    def correct(case: Case, calls: list[Call]) -> bool:
        return grade(case, calls).correct

    lisbon, oslo = weather(city="Lisbon"), weather(city="Oslo")
    shuffled = {"code": "5", "budget": 200, "date": "2026-03-02", "people": 4, "room": "Ada"}
    assert correct(book, [Call("book_room", shuffled)]), "argument order does not matter"
    assert correct(two, [oslo, lisbon]), "parallel calls match in any order"
    assert correct(zurich, [weather(unit="fahrenheit", city="Zurich")]), "any accepted answer may match"
    assert correct(two, [weather(city="Lisbon", unit="celsius"), oslo]), (
        "an omitted argument equals its schema default"
    )
    assert not correct(zurich, [weather(city="Zürich")]), (
        "an omitted argument is its default, not a wildcard"
    )
    assert not correct(zurich, [weather(city="zurich", unit="fahrenheit")]), (
        "strings compare exactly; variants are listed as accepted answers"
    )
    assert not correct(zurich, [Call("get_forecast", {"city": "Zürich", "unit": "fahrenheit"})]), (
        "the tool name must match too"
    )
    assert not correct(two, [lisbon, lisbon]), "each accepted call is matched once"
    assert not correct(two, [lisbon, oslo, lisbon]), "an extra call is wrong"
    assert not correct(two, [oslo]), "a missing call is wrong"
    assert not correct(two, [weather(city="Lisbon", lang="pt"), oslo]), (
        "an argument the schema does not define matches nothing"
    )
    assert not correct(two, [lisbon, Call("get_forecast", {"city": "Oslo"})]), (
        "a tool outside the catalog matches nothing"
    )
    assert correct(book, [booking(budget=200.0)]) and correct(book, [booking(budget=200)]), (
        "a number parameter compares by value"
    )
    assert not correct(book, [booking(budget=200, people=4.0)]), "an integer parameter needs an int"
    for coercible in (booking(budget=200, people="4"), booking(budget="200")):
        assert not correct(book, [coercible]), (
            "the checker grades what the model wrote; it does not coerce"
        )
    assert not correct(book, [booking(budget=200, code=5)]), "a string parameter needs a string"
    for one_sided in (booking(), booking(budget=200, note="window seat")):
        assert not correct(book, [one_sided]), (
            "a parameter without a default must be given on both sides"
        )
    assert typed(CASES) == untouched, "AST matching leaves the case unchanged"

    by_hand = [
        Call("read_file", {"path": "reports/q1.txt"}),
        Call("write_file", {"path": "reports/q1-final.txt", "text": Q1}),
        Call("delete_file", {"path": "reports/q1.txt"}),
        DELETE_NOTES,
    ]
    before = typed(rename_turns)
    assert grade(rename_turns, [MOVE, DELETE_NOTES]) == Verdict(
        "rename report", "multi_turn", True, ""
    ), "a multi-turn case that ends in the expected state is correct"
    assert typed(rename_turns) == before, "grading leaves the case unchanged"
    assert correct(rename_turns, by_hand), "a multi-turn case is graded on the state its calls leave"
    assert grade(rename_live, by_hand) == Verdict(
        "rename_report", "live", False, "no accepted answer matches"
    ), "a live case is graded on its calls, whatever state they leave"
    typo = Call("move_file", {"src": "reports/Q1.txt", "dst": "reports/q1-final.txt"})
    assert correct(rename_turns, [typo, MOVE, DELETE_NOTES]), (
        "a failed call changes nothing, and the replay goes on"
    )
    copied = [
        Call("copy_file", {"src": "reports/q1.txt", "dst": "reports/q1-final.txt"}),
        Call("delete_file", {"path": "reports/q1.txt"}),
        DELETE_NOTES,
    ]
    assert grade(rename_turns, copied) == Verdict(
        "rename report", "multi_turn", False, "final state differs"
    ), "only the tools the case offers can run"
    miswritten = Call("write_file", {"path": "count.txt", "text": 2})
    assert correct(rename_turns, [MOVE, miswritten, DELETE_NOTES]), (
        "a call with invalid arguments changes nothing"
    )
    assert not correct(rename_turns, [MOVE]), "a half-done task leaves the wrong state"
    retyped = [Call("write_file", {"path": "reports/q1-final.txt", "text": "Q1 revenue: 1.3M"}),
               Call("delete_file", {"path": "reports/q1.txt"}), DELETE_NOTES]
    assert not correct(rename_turns, retyped), "the state is compared file by file, text included"
    rewrite = [Call("write_file", {"path": "notes.txt", "text": "call Bo"}), DELETE_NOTES, MOVE]
    assert correct(rename_turns, rewrite), "calls replay in the order they were made"

    assert grade(no_tool, []) == Verdict("no tool/1", "hallucination", True, ""), (
        "calling nothing is right when no tool fits"
    )
    assert grade(no_tool, [weather(city="Canberra")]) == Verdict(
        "no tool/1", "hallucination", False, "a tool was called"
    ), "any call on a hallucination case is wrong, even to a real tool"
    assert grade(no_tool, None) == Verdict("no tool/1", "hallucination", False, "no attempt"), (
        "no attempt is not a refusal"
    )

    attempts = {
        "weather/zürich 3": [weather(city="Zürich", unit="fahrenheit")],
        "weather/two cities": [weather(city="Lisbon")],
        "rename_report": [DELETE_NOTES, MOVE],
        "book/ada 1": [booking(budget=200)],
        "rename report": [MOVE],
        "no tool/1": [],
    }
    report = score_run(CASES, attempts)
    assert report.counts == {
        "agentic": 1,
        "multi_turn": 1,
        "live": 3,
        "non_live": 1,
        "hallucination": 1,
    }, "verdicts are counted per category"
    assert report.scores == {
        "agentic": 0.0,
        "multi_turn": 0.0,
        "live": 2 / 3,
        "non_live": 1.0,
        "hallucination": 1.0,
    }, "accuracy per category; a case without an attempt is wrong"
    assert report.total == pytest.approx(0.1 * 2 / 3 + 0.1 + 0.1), (
        "categories are averaged first, then weighted 40/30/10/10/10"
    )
    partial = score_run(
        [zurich, two, book], {"weather/zürich 3": [], "book/ada 1": [booking(budget=200)]}
    )
    assert partial.scores["agentic"] is None and partial.counts["agentic"] == 0, (
        "a category without cases has no score"
    )
    assert partial.total == pytest.approx((0.1 * 0.0 + 0.1 * 1.0) / 0.2), (
        "the total leaves out empty categories and rescales the other weights"
    )
    assert score_run([no_tool], {}).scores["hallucination"] == 0.0, (
        "a case missing from the attempts had no attempt"
    )
    assert summarize([]).total is None, "no cases, no total"
    with pytest.raises(ValueError):
        score_run([zurich], {"weather/zürich 3": [], "weather/oslo 1": []})
    assert typed(CASES) == untouched, "grading leaves every case unchanged"


class ScriptedModel:
    """A stand-in for the model API: each case is answered after its delay."""

    def __init__(self, script: dict[str, tuple[float, object]]) -> None:
        self.script = script
        self.in_flight = 0
        self.peak = 0
        self.finished: list[str] = []
        self.cancelled: list[str] = []

    async def __call__(self, case: Case) -> list[Call]:
        delay, answer = self.script[case.case_id]
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            self.cancelled.append(case.case_id)
            raise
        finally:
            self.in_flight -= 1
        self.finished.append(case.case_id)
        if isinstance(answer, Exception):
            raise answer
        return answer


CLEAN_UP = [
    Call("search_files", {"query": "draft"}),
    Call("move_file", {"src": "reports/q2.txt", "dst": "archive/q2.txt"}),
    Call("move_file", {"src": "reports/q3.txt", "dst": "archive/q3.txt"}),
]


@pytest.mark.skip("Part 4")
def test_suite_tap(tmp_path) -> None:
    """Cases run concurrently; each gets its TAP line as soon as it is graded."""
    zurich, two, book, rename_live, rename_turns, clean_up, no_tool = CASES
    model = ScriptedModel({
        "clean up/2": (0.2, CLEAN_UP),
        "weather/zürich 3": (0.04, [weather(city="Zurich", unit="fahrenheit")]),
        "rename report": (0.08, [MOVE]),
        "no tool/1": (0.016, RuntimeError("model overloaded\nretry in 2 s")),
        "book/ada 1": (0.12, [booking(budget=200.0)]),
        "rename_report": (0.02, [Call("copy_file", {"src": "reports/q1.txt",
                                                    "dst": "reports/q1-final.txt"})]),
    })
    suite = [clean_up, zurich, rename_turns, no_tool, book, rename_live]

    async def run() -> list[tuple[int, str]]:
        return [(len(model.finished), line) async for line in run_suite(suite, model, concurrency=2)]

    received = within(run())
    rows = "".join(line for _, line in received).split("\n")
    assert rows.pop() == "", "every line ends with a newline"
    assert rows == [
        "ok 1 - weather/zürich 3 # live",
        "not ok 2 - rename report # multi_turn: final state differs",
        "not ok 3 - no tool/1 # hallucination: error: RuntimeError: model overloaded retry in 2 s",
        "ok 4 - clean up/2 # agentic",
        "not ok 5 - rename_report # live: no accepted answer matches",
        "ok 6 - book/ada 1 # non_live",
        "# score 0.5500",
        "1..6",
    ], "one line per case, numbered as cases finish; a failed model call is a wrong answer"
    assert model.peak == 2, "at most `concurrency` cases ask the model at once"
    assert received[0][0] == 1, "write each line as soon as its case is graded"

    stalled = ScriptedModel({"weather/zürich 3": (0.01, []), "clean up/2": (5.0, CLEAN_UP)})

    async def stop_early() -> tuple[str, list[str], int]:
        agen = run_suite([clean_up, zurich], stalled, concurrency=2)
        first = await agen.__anext__()
        await agen.aclose()
        return first, list(stalled.cancelled), stalled.in_flight

    first, cancelled, in_flight = within(stop_early())
    assert first == "not ok 1 - weather/zürich 3 # live: no accepted answer matches\n", (
        "the first case to finish is reported first"
    )
    assert (cancelled, in_flight) == (["clean up/2"], 0), (
        "a reader that stops early cancels the cases still running"
    )
    assert "".join(collect(run_suite([], stalled))) == "# score -\n1..0\n", (
        "an empty suite still ends with its score and its plan"
    )
    with pytest.raises(ValueError):
        collect(run_suite([zurich], stalled, concurrency=0))
    undescribed = dataclasses.replace(rename_turns, case_id="rename report/2", tools=[
        {"name": tool["name"], "input_schema": tool["input_schema"]} for tool in RENAME_TOOLS
    ])
    replies = ScriptedModel({"rename report/2": (0.0, [MOVE])})
    assert "".join(collect(run_suite([undescribed], replies))) == (
        "not ok 1 - rename report/2 # multi_turn: error: KeyError: 'description'\n"
        "# score 0.0000\n1..1\n"
    ), "a grading that raises makes its case not ok too"

    bank = CaseBank(str(tmp_path / "cases"))
    for case in CASES:
        bank.add(case)
    answers = ScriptedModel({
        "rename_report": (0.0, [MOVE, DELETE_NOTES]),
        "weather/two cities": (0.0, [weather(city="Oslo")]),
        "weather/zürich 3": (0.0, [weather(city="Zürich", unit="fahrenheit")]),
    })
    lines = "".join(collect(EvalService(bank, concurrency=1).run(answers, category="live")))
    bank.close()
    assert lines.split("\n") == [
        "ok 1 - rename_report # live",
        "not ok 2 - weather/two cities # live: no accepted answer matches",
        "ok 3 - weather/zürich 3 # live",
        "# score 0.6667",
        "1..3",
        "",
    ], "the service runs the bank's cases in id order"


LOOKUP = {
    "count": 2,
    "owner": None,
    "tickets": [
        {"id": "T-7", "subject": "$c1.result.owner", "tags": ["urgent", "billing"]},
        {"id": "T-9", "subject": "refund twice", "tags": []},
    ],
}


@pytest.mark.skip("Part 5")
def test_call_chains() -> None:
    """References into earlier results resolve through nested fields and indexes, in order."""
    drive = FakeDrive(drive_state())
    chain = [
        Step("call_1", "search_files", {"query": "draft"}),
        Step("call_2", "move_file", {"src": "$call_1.result.hits[0].path", "dst": "archive/q2.txt"}),
        Step("call_3", "move_file", {"src": "$call_1.result.hits[1].path", "dst": "archive/q3.txt"}),
    ]
    original = copy.deepcopy(chain)
    ran = run_chain(chain, drive.call)
    assert ran[1:] == [
        Ran("call_2", "move_file", {"src": "reports/q2.txt", "dst": "archive/q2.txt"},
            {"path": "archive/q2.txt"}),
        Ran("call_3", "move_file", {"src": "reports/q3.txt", "dst": "archive/q3.txt"},
            {"path": "archive/q3.txt"}),
    ], "a reference becomes the value it points at"
    assert drive.state == CASES[5].expected_state, "the recorded chain reproduces the agentic case"
    assert chain == original, "the chain itself is not changed"

    log: list[str] = []

    def execute(name: str, args: dict) -> object:
        log.append(name)
        return copy.deepcopy({"lookup": LOOKUP, "status": "closed"}.get(name, {"ok": True}))

    ran = run_chain([
        Step("c1", "lookup", {"text": "refund"}),
        Step("c2", "status", {"ticket": "$c1.result.tickets[0].id"}),
        Step("c3", "notify", {
            "to": {
                "ids": ["$c1.result.tickets[0].id", "$c1.result.tickets[1].id"],
                "owner": "$c1.result.owner",
            },
            "limit": "$c1.result.count",
            "tags": "$c1.result.tickets[0].tags",
            "first_tag": "$c1.result.tickets[0].tags[1]",
            "state": "$c2.result",
            "subject": "$c1.result.tickets[0].subject",
            "note": "count is $c1.result.count",
            "price": "$5 off",
        }),
    ], execute)
    assert ran[1].args == {"ticket": "T-7"}, "a reference becomes the value it points at"
    assert ran[2].args == {
        "to": {"ids": ["T-7", "T-9"], "owner": None},
        "limit": 2,
        "tags": ["urgent", "billing"],
        "first_tag": "billing",
        "state": "closed",
        "subject": "$c1.result.owner",
        "note": "count is $c1.result.count",
        "price": "$5 off",
    }, "references resolve at any depth, keep their type, and results are never resolved again"
    assert log == ["lookup", "status", "notify"], "a call referred to many times still runs once"

    def failure(steps: list[Step]) -> ChainError:
        log.clear()
        with pytest.raises(ChainError) as caught:
            run_chain(steps, execute)
        return caught.value

    for steps, why in (
        ([Step("c1", "lookup", {}), Step("c2", "status", {"t": "$c3.result.id"}),
          Step("c3", "lookup", {})], "a later call"),
        ([Step("c1", "lookup", {}), Step("c2", "status", {"t": ["$c2.result"]})], "the call itself"),
        ([Step("c1", "lookup", {}), Step("c2", "status", {"t": {"id": "$c9.result.id"}})],
         "an unknown call"),
    ):
        error = failure(steps)
        assert (error.call_id, log) == ("c2", []), (
            f"a reference to {why} is rejected before anything runs"
        )
    error = failure([Step("c1", "lookup", {}), Step("c1", "status", {})])
    assert (error.call_id, log) == ("c1", []), (
        "two steps cannot share a call id; the chain is rejected before anything runs"
    )
    for bad in ("$c1.result.tickets[-1].id", "$c1.result.tickets.0", "$c1.result.", "$c1.results",
                "$c1.result[x]"):
        error = failure([Step("c1", "lookup", {}), Step("c2", "status", {"t": bad})])
        assert (error.call_id, error.ref, log) == ("c2", bad, []), (
            f"{bad!r} starts like a reference but does not parse"
        )
    for ref, at in (
        ("$c1.result.tickets[2].id", "$c1.result.tickets[2]"),
        ("$c1.result.tickets[0].owner", "$c1.result.tickets[0].owner"),
        ("$c1.result.owner.name", "$c1.result.owner.name"),
        ("$c1.result.tickets.id", "$c1.result.tickets.id"),
        ("$c1.result[0]", "$c1.result[0]"),
        ("$c2.result.state", "$c2.result.state"),
        ("$c2.result[0]", "$c2.result[0]"),
    ):
        error = failure([Step("c1", "lookup", {}), Step("c2", "status", {}),
                         Step("c3", "notify", {"x": {"y": [ref]}})])
        assert (error.call_id, error.ref, error.at) == ("c3", ref, at), (
            f"{ref} cannot be followed past {at}"
        )
        assert log == ["lookup", "status"], "a step whose reference cannot be followed does not run"
