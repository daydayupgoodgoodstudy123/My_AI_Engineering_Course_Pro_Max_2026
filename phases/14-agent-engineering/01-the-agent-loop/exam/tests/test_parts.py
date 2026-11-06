import asyncio
import dataclasses
import json
import os
import re
import time
from functools import partial

import pytest
from reactloop.formatter import TRUNCATED, format_observation
from reactloop.loop import AgentLoop, to_observation
from reactloop.messages import Message, ToolCall
from reactloop.model import ScriptedModel, ScriptedTextModel
from reactloop.react import FORMAT_ERROR, parse_step, run_react
from reactloop.stream import stream_run
from reactloop.tools import KVStore, ToolRegistry, calculator
from reactloop.transcript import load_transcript, save_transcript

STOCK = {"A-1": {"qty": "12"}, "B-2": {"qty": None}}


def stock(sku: str) -> int:
    """Units in stock for a SKU. B-2's count is missing upstream."""
    return int(STOCK[sku]["qty"])


def shop_tools() -> ToolRegistry:
    tools = ToolRegistry()
    kv = KVStore()
    tools.register("calculator", calculator)
    tools.register("kv_get", kv.get)
    tools.register("kv_set", kv.set)
    tools.register("stock", stock)
    return tools


def observations(request: list[Message]) -> list[str]:
    """The observation strings a model request carried."""
    return [m.content for m in request if m.role == "tool"]


def call(name: str, **args) -> dict:
    return {"name": name, "args": args}


def report_page(n: int) -> dict:
    """One page of a stock report: about 500 characters of JSON."""
    return {
        "page": n,
        "rows": [
            {"id": n * 10 + i, "sku": f"SKU-{n:04d}-{i}", "name": "Grüntee, lose", "qty": 3 * i, "price": 4.5 + i, "tags": ["tea", "loose", "bio"]}
            for i in range(4)
        ],
    }


class Pager:
    """Reads a long report one page per turn, then answers. It only looks at the latest message."""

    def __init__(self, pages: int) -> None:
        self.pages = pages
        self.turns = 0

    def respond(self, messages: list[Message]) -> dict:
        self.turns += 1
        if self.turns <= self.pages:
            return {"tool_calls": [call("read_page", n=self.turns)]}
        return {"text": f"read {self.pages} pages"}


@pytest.mark.skip("Part 1")
def test_agent_loop() -> None:
    """The loop stops when a turn has no tool calls, hands reasoning back, and reports tool errors truthfully."""
    model = ScriptedModel([{"text": "Paris is the capital of France."}])
    outcome = AgentLoop(model, shop_tools()).run("What is the capital of France?")
    assert (outcome.answer, outcome.stop) == ("Paris is the capital of France.", "no_tool_calls"), (
        "a turn without tool calls is the answer"
    )
    assert [m.role for m in outcome.history] == ["user", "assistant"]
    outcome = AgentLoop(ScriptedModel([{"thinking": "Nothing left to do."}]), shop_tools()).run("Thanks!")
    assert (outcome.answer, outcome.stop) == ("", "no_tool_calls"), "a turn without tool calls ends the run, text or not"

    model = ScriptedModel(
        [
            {
                "thinking": "Tax is 15% of the base price.",
                "text": "Let me work out the tax first.",
                "tool_calls": [call("calculator", expr="120 * 0.15")],
            },
            {
                "thinking": "Store it, then add it up.",
                "tool_calls": [call("kv_set", key="tax", value="18.0"), call("calculator", expr="120 + 18.0")],
            },
            {"thinking": "Done.", "text": "The total including 15% tax is 138.0.", "tool_calls": []},
        ]
    )
    outcome = AgentLoop(model, shop_tools()).run("What is 120 plus 15% tax?")
    assert (outcome.answer, outcome.stop) == ("The total including 15% tax is 138.0.", "no_tool_calls"), (
        "text next to a tool call is not the answer yet"
    )
    assert [m.role for m in outcome.history] == ["user", "assistant", "tool", "assistant", "tool", "tool", "assistant"]
    assert observations(model.requests[2]) == ["18.0", "stored tax", "138.0"], "the model reads every observation"
    assert [m.reasoning for m in outcome.history if m.role == "assistant"] == model.issued, (
        "every assistant turn keeps the reasoning item it came with"
    )

    model = ScriptedModel([{"tool_calls": [call("finish", answer="138.0")]}])
    outcome = AgentLoop(model, shop_tools()).run("Just the total, please.")
    assert (outcome.answer, outcome.stop) == ("138.0", "finish"), "finish is an explicit stop"

    model = ScriptedModel(
        [
            {
                "tool_calls": [
                    call("stock", item="A-1"),
                    call("stock", sku="A-1", warehouse="north"),
                    call("kv_set", key="tax"),
                    call("stock", sku="B-2"),
                    call("stock", sku="Z-9"),
                    call("restock", sku="B-2"),
                    call("stock", sku="A-1"),
                ]
            },
            {"text": "A-1 has 12 units. B-2's count is broken upstream."},
        ]
    )
    AgentLoop(model, shop_tools()).run("How many A-1 and B-2 do we have?")
    seen = observations(model.requests[1])
    assert (
        seen[0].startswith("error: bad args for stock: ")
        and seen[1].startswith("error: bad args for stock: ")
        and seen[2].startswith("error: bad args for kv_set: ")
    ), "arguments that do not fit the tool are bad args"
    assert seen[3].startswith("error: TypeError: int() argument"), (
        "a TypeError raised inside the tool is the tool's own error, not bad args"
    )
    assert seen[4:] == ["error: KeyError: 'Z-9'", "error: unknown tool 'restock'", "12"]
    assert shop_tools().dispatch(ToolCall("stock", ["A-1", "north"])).startswith("error: bad args for stock: "), (
        "positional arguments are checked the same way"
    )

    pages = [report_page(n) for n in range(1, 1001)]
    tools = ToolRegistry()
    tools.register("read_page", lambda n: pages[n - 1])
    start = time.perf_counter()
    outcome = AgentLoop(Pager(len(pages)), tools, max_turns=5000).run("Sum up the stock report")
    elapsed = time.perf_counter() - start
    assert outcome.answer == "read 1000 pages"
    assert elapsed < 0.12, "a long run must not slow down as its history grows"
    tool_turns = [m for m in outcome.history if m.role == "tool"]
    assert [m.content for m in tool_turns] == [to_observation(p) for p in pages], (
        "the history keeps every observation the model read"
    )
    assert [m.result for m in tool_turns] == pages, "the history keeps the raw result behind each observation"


def exact(value):
    """A comparable form that tells -0.0 from 0.0, 1 from 1.0 and True, bytes from str, a ToolCall from a dict."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, {f.name: exact(getattr(value, f.name)) for f in dataclasses.fields(value)})
    if isinstance(value, dict):
        return ("dict", {key: exact(item) for key, item in value.items()})
    if isinstance(value, list):
        return ("list", [exact(item) for item in value])
    if isinstance(value, float):
        return ("float", value.hex())
    return (type(value).__name__, value)


ORDER_ID = 1_855_302_148_811_472_901  # the shop API's ids are larger than 2**53
NOTE = "Bitte bei Müller klingeln \ud83d"  # the courier API cut its note in the middle of an emoji


def find_order(ref: str) -> dict:
    return {
        "order_id": ORDER_ID,
        "ref": ref,
        "status": "unterwegs",
        "temp_delta": -0.0,
        "weight_kg": 0.1 + 0.2,
        "items": [["Grüntee", 2], ["Tasse", 1]],
        "fragile": True,
        "gift_note": None,
    }


def courier_note(order_id: int) -> str:
    return NOTE if order_id == ORDER_ID else "unknown order"


def order_tools() -> ToolRegistry:
    tools = ToolRegistry()
    tools.register("find_order", find_order)
    tools.register("courier_note", courier_note)
    return tools


def readable(path):
    try:
        return load_transcript(path)
    except ValueError:
        return None


@pytest.mark.skip("Part 2")
def test_transcript_snapshot(tmp_path) -> None:
    """A transcript is one JSON snapshot that reads back exactly, so a run can be debugged and continued."""
    path = tmp_path / "run.json"
    model = ScriptedModel(
        [
            {"thinking": "Look the order up first.", "tool_calls": [call("find_order", ref="Zürich-7")]},
            {
                "thinking": "Ask the courier.",
                "text": "Ich frage beim Kurier nach.",
                "tool_calls": [call("courier_note", order_id=ORDER_ID)],
            },
            {"thinking": "Answer in German.", "text": "Ihre Bestellung ist unterwegs. 🚚"},
        ],
        seed=7,
    )
    run = AgentLoop(model, order_tools()).run("Wo ist meine Bestellung Zürich-7?")
    save_transcript(path, run.history)
    assert exact(load_transcript(path)) == exact(run.history), "a transcript reads back exactly"

    later = ScriptedModel([{"thinking": "Give the slot.", "text": "Morgen zwischen 9 und 12 Uhr."}], seed=8)
    resumed = AgentLoop(later, order_tools(), history=load_transcript(path)).run("Wann kommt sie an?")
    assert resumed.answer == "Morgen zwischen 9 und 12 Uhr."
    assert exact(later.requests[0][: len(run.history)]) == exact(run.history), "a run goes on from a loaded transcript"

    small = [
        Message("user", "Wie spät ist es in Zürich?"),
        Message(
            "assistant",
            tool_calls=[ToolCall("clock", {"tz": "Europe/Zurich"})],
            reasoning=b"\xfb\xff\x00rs",
            thinking="Ask the clock.",
        ),
        Message("tool", '{"time": "09:30", "dst": false}', name="clock", result={"time": "09:30", "dst": False}),
        Message("assistant", "Es ist 09:30."),
    ]
    save_transcript(path, small)
    blank = {"content": "", "tool_calls": [], "reasoning": None, "thinking": "", "name": "", "result": None}
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": 1,
        "messages": [
            {**blank, "role": "user", "content": "Wie spät ist es in Zürich?"},
            {
                **blank,
                "role": "assistant",
                "tool_calls": [{"name": "clock", "args": {"tz": "Europe/Zurich"}}],
                "reasoning": "+/8AcnM=",
                "thinking": "Ask the clock.",
            },
            {
                **blank,
                "role": "tool",
                "content": '{"time": "09:30", "dst": false}',
                "name": "clock",
                "result": {"time": "09:30", "dst": False},
            },
            {**blank, "role": "assistant", "content": "Es ist 09:30."},
        ],
    }, "the snapshot keeps the layout the trace viewer reads: asdict fields, reasoning as standard base64"

    if os.name == "posix":  # Windows will not replace a file that is open
        with open(path, encoding="utf-8") as viewer:  # the trace viewer has the old snapshot open
            save_transcript(path, run.history)
            assert json.loads(viewer.read())["messages"][0]["content"] == "Wie spät ist es in Zürich?", (
                "a save puts a whole new file in place: a reader of the old one still reads the old one"
            )
    else:
        save_transcript(path, run.history)
    assert exact(load_transcript(path)) == exact(run.history), "a save replaces the snapshot"
    assert json.loads(path.read_text(encoding="utf-8"))["messages"][4]["result"] == NOTE, (
        "the trace viewer reads the snapshot as UTF-8 JSON"
    )
    assert os.listdir(tmp_path) == ["run.json"], "a save leaves nothing else behind"

    tags = Message("tool", "['gift', 'fragile']", name="tags", result={"gift", "fragile"})  # a set: JSON cannot hold it
    with pytest.raises((TypeError, ValueError)):
        save_transcript(path, small + [tags])
    assert exact(readable(path)) == exact(run.history), "a save that fails leaves the earlier snapshot in place"
    assert os.listdir(tmp_path) == ["run.json"], "a save that fails leaves nothing behind"


@pytest.mark.skip("Part 3")
def test_react_text() -> None:
    """A text model's ReAct steps are read strictly, and only the runtime writes observations."""
    step = parse_step('Thought: I need to look up the capital of France.\nAction: search("capital of France")')
    assert (step.thought, step.action, step.args) == (
        "I need to look up the capital of France.",
        "search",
        ["capital of France"],
    )
    first = (
        "Thought: The rent is in the facilities notes,\n"
        'under "Paris". The next Action: is a search, then an Observation: comes back.\n'
        'Action: search("office rent, Paris (France)")\n'
        "Observation: The rent is 9000 EUR.\n"
        "Thought: So the tax is 1350 EUR.\n"
        'Action: finish("1350 EUR")'
    )
    step = parse_step(first)
    assert step.thought == (
        'The rent is in the facilities notes,\nunder "Paris". The next Action: is a search, then an Observation: comes back.'
    ), "a Thought goes on until the Action line"
    assert (step.action, step.args) == ("search", ["office rent, Paris (France)"]), (
        "commas and parentheses inside an argument belong to it"
    )
    assert step.text == first[: first.index("\nObservation:")], "the step ends at its Action line"
    step = parse_step('Thought: Both at once.\nAction: search("Paris")\nAction: finish("Paris")')
    assert (step.action, step.args, step.text) == ("search", ["Paris"], 'Thought: Both at once.\nAction: search("Paris")'), (
        "only the first Action line counts, and the step ends with it"
    )

    for text, expected in [
        ('Action: finish("He said \\"hi\\" (twice)")', ("finish", ['He said "hi" (twice)'])),
        ('Action: open_file("C:\\\\")', ("open_file", ["C:\\"])),
        ('Action: search("caf\\u00e9,\\nmenu")', ("search", ["café,\nmenu"])),
        ('Action: search("Zürich, 東京")', ("search", ["Zürich, 東京"])),
        ('Action: kv_set("tax", "18.0")', ("kv_set", ["tax", "18.0"])),
        ('Action:  kv_store.get( "base" )  ', ("kv_store.get", ["base"])),
        ("Action: list_keys()", ("list_keys", [])),
    ]:
        step = parse_step(text)
        assert (step.action, step.args) == expected, f"read the action in {text!r}"

    for text in [
        "Action: search('capital of France')",
        'Action: search("capital of France"',
        'Action: search("capital of France)',
        'Action: search("capital", )',
        "Action: kv_get(42)",
        'Action: search("Paris") and then finish',
        'Action: finish("Paris", "France")',
        "Action: finish()",
        "Action: search",
        'Thought: I know this one.\nObservation: Paris.\nAction: finish("Paris")',
        'Observation: Paris is the capital.\nAction: finish("Paris")',
        "Thought: Paris, surely.",
    ]:
        step = parse_step(text)
        assert step.action is None and step.error, f"no readable action in {text!r}"
    assert parse_step('Action: search("Lieferung \\ud83d\\ude9a")').args == ["Lieferung 🚚"], (
        "an escaped surrogate pair is one character, as in JSON"
    )

    searched: list[str] = []

    def search(query: str) -> list[str]:
        searched.append(query)
        notes = {"office rent, Paris (France)": ["Rent for the Paris office: 1200 EUR a month."]}
        return notes.get(query, [])

    tools = ToolRegistry()
    tools.register("search", search)
    tools.register("calculator", calculator)
    blocks = [
        first,
        "Thought: 15% of 1200.\nAction: calculator('1200 * 0.15')",
        'Thought: Double quotes, then.\nAction: calculator("(1200 * 15) / 100")',
        'Thought: Let me check the notes once more.\nObservation: The notes say 180 EUR.\nAction: finish("180 EUR")',
        'Thought: The tax is 180.0 EUR.\nAction: finish("180.0 EUR (15% of \\"1200 EUR\\")")',
    ]
    model = ScriptedTextModel(blocks)
    run = run_react(model, tools, "What is 15% tax on the Paris office rent?")
    assert run.answer == '180.0 EUR (15% of "1200 EUR")', "finish's argument is the answer"
    assert [s.action for s in run.steps] == ["search", None, "calculator", None, "finish"]
    assert searched == ["office rent, Paris (France)"], "an action runs once, with its whole argument"
    scratchpad = ["Question: What is 15% tax on the Paris office rent?\n"]
    for text, observation in [
        (first[: first.index("\nObservation:")], '["Rent for the Paris office: 1200 EUR a month."]'),
        (blocks[1], FORMAT_ERROR),
        (blocks[2], "180.0"),
        ("Thought: Let me check the notes once more.", FORMAT_ERROR),
    ]:
        scratchpad.append(scratchpad[-1] + f"{text}\nObservation: {observation}\n")
    assert model.prompts == scratchpad, "each prompt carries every step so far, with the runtime's observations"


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


def sse_events(frames: list[str]) -> list[tuple[str, str]]:
    """(event, data) for each item, parsed the way a browser's EventSource reads text/event-stream."""
    events = []
    for frame in frames:
        lines = re.split(r"\r\n|\r|\n", frame)
        assert lines[-2:] == ["", ""] and "" not in lines[:-2], "each item is one event, ending in a blank line"
        kind, data = "message", None
        for line in lines[:-2]:
            if line.startswith(":"):
                continue
            name, colon, value = line.partition(":")
            if colon and value.startswith(" "):
                value = value[1:]
            if name == "event":
                kind = value
            elif name == "data":
                data = value if data is None else data + "\n" + value
        if data is not None:  # an event without data is never dispatched
            events.append((kind, json.loads(data) if kind == "action" else data))
    return events


@pytest.mark.skip("Part 4")
def test_stream_events() -> None:
    """A run streams as server-sent events, each as it happens, with the reasoning on its own channel."""
    ran: list[str] = []

    def menu() -> str:
        ran.append("menu")
        return "Grüntee 4.50\u2028Schwarztee 3.90"  # the menu text separates its lines with U+2028

    def install(package: str) -> str:
        ran.append(package)
        return f"Downloading {package}... 10%\rDownloading {package}... 100%\nDone"

    def notes(item: str) -> str:
        ran.append(f"notes:{item}")
        return ""

    tools = ToolRegistry()
    tools.register("menu", menu)
    tools.register("install", install)
    tools.register("notes", notes)
    script = [
        {
            "thinking": ["Plan:\r\n  1. read the menu", "\n  2. check the notes"],
            "text": "Checking the menu.",
            "tool_calls": [call("menu"), call("notes", item="Grüntee")],
        },
        {"thinking": "The price printer needs its driver.", "tool_calls": [call("install", package="labelprint")]},
        {
            "thinking": "Green tea is 4.50.",
            "text": "Fertig.",
            "tool_calls": [call("finish", answer="Grüntee kostet 4.50 EUR.\n\nSchwarztee 3.90 EUR.")],
        },
    ]
    model = ScriptedModel(script, seed=3)
    loop = AgentLoop(model, tools)
    received = []

    async def watch() -> None:
        async for frame in stream_run(loop, "Was kostet Grüntee?"):
            for event in sse_events([frame]):
                received.append((event, model.sent, len(ran)))

    asyncio.run(watch())
    assert [event for event, _, _ in received] == [
        ("reasoning", "Plan:\n  1. read the menu"),
        ("reasoning", "\n  2. check the notes"),
        ("action", {"name": "menu", "args": {}}),
        ("observation", "Grüntee 4.50\u2028Schwarztee 3.90"),
        ("action", {"name": "notes", "args": {"item": "Grüntee"}}),
        ("observation", ""),
        ("reasoning", "The price printer needs its driver."),
        ("action", {"name": "install", "args": {"package": "labelprint"}}),
        ("observation", "Downloading labelprint... 10%\nDownloading labelprint... 100%\nDone"),
        ("reasoning", "Green tea is 4.50."),
        ("final", "Grüntee kostet 4.50 EUR.\n\nSchwarztee 3.90 EUR."),
    ], "reasoning, actions, observations and one final answer, each on its own channel, line for line"
    assert [(sent, tools_run) for _, sent, tools_run in received] == [
        (1, 0), (2, 0), (2, 0), (2, 1), (2, 1), (2, 2), (3, 2), (3, 2), (3, 3), (4, 3), (4, 3),
    ], "each event is sent as soon as it happens"

    twin = AgentLoop(ScriptedModel(script, seed=3), tools)
    assert exact(loop.history) == exact(twin.run("Was kostet Grüntee?").history), (
        "a streamed run leaves the same history as run()"
    )

    hello = AgentLoop(ScriptedModel([{"thinking": "A greeting.", "text": "Hallo!"}]), tools)
    assert sse_events(collect(stream_run(hello, "Hallo?"))) == [("reasoning", "A greeting."), ("final", "Hallo!")], (
        "a turn without tool calls is the final answer"
    )


@pytest.mark.skip("Part 5")
def test_nested_observation() -> None:
    """Nested tool results become short observations that come out the same every time, cycles and all."""
    order = {"status": "shipped", "id": 7, "items": ["A-1", "B-2"], "paid": True, "note": None, "total": {"eur": 12.5, "vat": 0.0}}
    assert format_observation(order) == (
        '{"id": 7, "items": ["A-1", "B-2"], "note": null, "paid": true, "status": "shipped", "total": {"eur": 12.5, "vat": 0.0}}'
    ), "keys in sorted order, values as JSON"
    assert format_observation(dict(reversed(list(order.items())))) == format_observation(order), (
        "the same result gives the same observation"
    )
    assert format_observation({"etag": "b", "ETag": "a", "Accept": "c"}) == '{"Accept": "c", "ETag": "a", "etag": "b"}', (
        "keys in plain sorted() order"
    )
    assert format_observation({"rows": list(range(1, 12)), "pos": (3, 4)}, max_items=3) == (
        '{"pos": [3, 4], "rows": [1, 2, 3, … 8 more]}'
    ), "a container shows at most max_items entries"
    assert format_observation({"a": 1, "b": 2, "c": 3}, max_items=3) == '{"a": 1, "b": 2, "c": 3}', (
        "nothing is left out when everything fits"
    )
    assert format_observation({"d": 4, "c": 3, "b": 2, "a": 1}, max_items=2) == '{"a": 1, "b": 2, … 2 more}', (
        "a dict shows its first keys in sorted order"
    )
    deep = {"a": {"b": {"c": {"d": 1}}, "e": [], "f": {}}, "g": [[1], ()]}
    assert format_observation(deep, max_depth=2) == '{"a": {"b": {…}, "e": [], "f": {}}, "g": [[…], []]}', (
        "containers below max_depth are elided, empty ones are not"
    )
    assert format_observation({"text": 'line 1\nline 2\t"quoted" \\ end', "city": "Zürich 🚚", "Straße": "Nr. 1"}) == (
        '{"Straße": "Nr. 1", "city": "Zürich 🚚", "text": "line 1\\nline 2\\t\\"quoted\\" \\\\ end"}'
    ), "strings inside a result are JSON strings"
    assert format_observation({"D:\\Backup": 3, "C:\\Users": 12}) == '{"C:\\\\Users": 12, "D:\\\\Backup": 3}', (
        "keys are JSON strings too"
    )
    assert format_observation("plain text\nstays as it is") == "plain text\nstays as it is", (
        "a string result is the observation as it is"
    )

    page = {"title": "Docs", "children": []}
    for title in ("Intro", "Setup", "FAQ"):
        page["children"].append({"title": title, "parent": page})
    assert format_observation(page, max_depth=4) == (
        '{"children": [{"parent": [cycle], "title": "Intro"}, {"parent": [cycle], "title": "Setup"}, '
        '{"parent": [cycle], "title": "FAQ"}], "title": "Docs"}'
    ), "a container inside itself is written [cycle]"
    ring = [1]
    ring.append(ring)
    assert format_observation(ring) == "[1, [cycle]]"
    ana = {"name": "Ana", "id": 3}
    thread = {"post": {"author": ana}, "reply": {"author": ana, "to": {"author": ana}}}
    assert format_observation(thread, max_depth=4) == (
        '{"post": {"author": {"id": 3, "name": "Ana"}}, '
        '"reply": {"author": {"id": 3, "name": "Ana"}, "to": {"author": {"id": 3, "name": "Ana"}}}}'
    ), "the same object reached twice is not a cycle"

    memo = {"city": "東京", "notes": "多言語のメモ。" * 40}
    cut = format_observation(memo, budget=60)
    assert len(cut) == 60 and cut.endswith(TRUNCATED), "an observation is at most budget characters, marker included"
    assert cut == format_observation(memo, budget=10**6)[: 60 - len(TRUNCATED)] + TRUNCATED, (
        "the budget counts characters"
    )
    assert format_observation("x" * 60, budget=60) == "x" * 60, "a result that fits is not cut"
    assert format_observation("y" * 100, budget=20) == "y" * 8 + TRUNCATED, "a string result is held to the budget too"

    tools = ToolRegistry()
    tools.register("open_page", lambda slug: page)
    model = ScriptedModel(
        [{"tool_calls": [call("open_page", slug="docs"), call("close_page")]}, {"text": "The docs have three pages."}]
    )
    observe = partial(format_observation, max_items=2, max_depth=4, budget=200)
    AgentLoop(model, tools, observe=observe).run("What is in the docs?")
    assert observations(model.requests[1]) == [
        '{"children": [{"parent": [cycle], "title": "Intro"}, {"parent": [cycle], "title": "Setup"}, … 1 more], '
        '"title": "Docs"}',
        "error: unknown tool 'close_page'",
    ], "the loop's observations come from the formatter"
