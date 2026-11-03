import asyncio
import json
import random
import struct
import time

import pytest
from fanout.calllog import CallLog, Record, done, started
from fanout.calls import ToolCall
from fanout.host import replay_and_execute, resume, run_parallel
from fanout.live import stream_results
from fanout.partial import PartialArguments
from fanout.schedule import Plan, PlannedCall, Slot, plan_fanout

LATENCY_S = {"Bengaluru": 0.05, "Tokyo": 0.1, "Zurich": 0.15}
TEMP_C = {"Bengaluru": 27, "Tokyo": 19, "Zurich": 4}


class WeatherAPI:
    """A stand-in weather service: each city answers after its own latency, unknown cities fail."""

    def __init__(self, pulled: list | None = None) -> None:
        self.calls: list[tuple[str, int]] = []  # (city, stream events read when the call began)
        self.pulled = pulled if pulled is not None else []

    async def __call__(self, city: str, units: str = "metric") -> dict:
        self.calls.append((city, len(self.pulled)))
        if city not in LATENCY_S:
            raise LookupError(f"no weather station in {city}")
        await asyncio.sleep(LATENCY_S[city])
        return {"city": city, "temp_c": TEMP_C[city]}

    def cities(self) -> list[str]:
        return [city for city, _ in self.calls]


def start(index: int, call_id: str, name: str = "get_weather") -> dict:
    return {"type": "call_start", "index": index, "id": call_id, "name": name}


def delta(index: int, chunk: str) -> dict:
    return {"type": "args_delta", "index": index, "chunk": chunk}


def stop(index: int) -> dict:
    return {"type": "call_stop", "index": index}


def cancel(index: int) -> dict:
    return {"type": "call_cancel", "index": index}


def finish(reason: str) -> dict:
    return {"type": "finish", "finish_reason": reason}


async def replay(events: list[dict], pulled: list | None = None):
    """The model's side of a streamed turn: one event at a time, with the host free to run in between."""
    for event in events:
        if pulled is not None:
            pulled.append(event)
        yield event
        await asyncio.sleep(0)


CITY_TURN = [
    start(0, "call_A"),
    start(1, "call_B"),
    delta(0, '{"city"'),
    start(2, "call_C"),
    delta(1, '{"city'),
    delta(0, ': "Zur'),
    delta(2, '{"city": "Beng'),
    delta(0, 'ich"}'),
    stop(0),
    delta(1, '": "Tokyo"}'),
    stop(1),
    delta(2, 'aluru"}'),
    stop(2),
]


@pytest.mark.skip("Part 1")
def test_replay_turn() -> None:
    """Interleaved fragments are put back together per call, and every answer goes back under its own id."""
    pulled: list[dict] = []
    weather = WeatherAPI(pulled)
    messages = asyncio.run(replay_and_execute(replay(CITY_TURN, pulled), {"get_weather": weather}))
    assert {m["tool_call_id"]: json.loads(m["content"])["city"] for m in messages} == {
        "call_A": "Zurich",
        "call_B": "Tokyo",
        "call_C": "Bengaluru",
    }, "every answer goes back under the id of the call that produced it"
    assert sorted(weather.cities()) == ["Bengaluru", "Tokyo", "Zurich"], "each call runs exactly once"
    began = dict(weather.calls)
    for city, stop_position in (("Zurich", 8), ("Tokyo", 10), ("Bengaluru", 12)):
        assert began[city] > stop_position, "a call starts only after its call_stop"
    assert began["Zurich"] < len(CITY_TURN), (
        "a call starts at its call_stop, while the rest of the turn is still streaming"
    )
    assert [m["tool_call_id"] for m in messages] == ["call_C", "call_B", "call_A"], (
        "reply in completion order"
    )
    assert all(m["role"] == "tool" for m in messages), "every answer is a tool message"

    flaky = [
        start(0, "call_D"),
        delta(0, '{"city": "Atlantis"}'),
        start(1, "call_E"),
        stop(0),
        delta(1, '{"city": "Tokyo"}'),
        stop(1),
    ]
    messages = asyncio.run(replay_and_execute(replay(flaky), {"get_weather": WeatherAPI()}))
    assert {m["tool_call_id"]: json.loads(m["content"]) for m in messages} == {
        "call_D": {"error": "LookupError: no weather station in Atlantis"},
        "call_E": {"city": "Tokyo", "temp_c": 19},
    }, "a failing tool is answered with its error, and the other calls still answer"

    in_flight: set[int] = set()
    peak = 0

    async def ping(n: int) -> dict:
        nonlocal peak
        in_flight.add(n)
        peak = max(peak, len(in_flight))
        await asyncio.sleep(0.008)
        in_flight.discard(n)
        return {"n": n}

    async def timed(coro):
        began = time.perf_counter()
        result = await coro
        return result, time.perf_counter() - began

    batch = [ToolCall(f"call_{n:03d}", "ping", {"n": n}) for n in range(250)]
    messages, elapsed = asyncio.run(timed(run_parallel(batch, {"ping": ping})))
    assert elapsed < 0.2, "the calls of a turn run at the same time: the turn takes as long as its slowest call"
    assert sorted(m["tool_call_id"] for m in messages) == [call.id for call in batch], "one answer per call"
    assert peak == len(batch), "every call of the turn is in flight at once"

    async def clock(tz: str) -> dict:
        raise ConnectionError("clock service unreachable")

    calls = [
        ToolCall("call_A", "get_weather", {"city": "Zurich"}),
        ToolCall("call_D", "get_weather", {"city": "Atlantis"}),
        ToolCall("call_B", "get_weather", {"city": "Tokyo"}),
        ToolCall("call_T", "get_time", {"tz": "Asia/Tokyo"}),
        ToolCall("call_C", "get_weather", {"city": "Bengaluru"}),
    ]
    messages = asyncio.run(run_parallel(calls, {"get_weather": WeatherAPI(), "get_time": clock}))
    assert [m["tool_call_id"] for m in messages] == ["call_D", "call_T", "call_C", "call_B", "call_A"], (
        "reply in completion order, failures included"
    )


STATUS_BYTE = {"started": 1, "done": 2}


def frame(record: Record) -> bytes:
    """One record, laid out as the fanout/calllog.py docstring describes."""
    call_id = record.call_id.encode()
    body = struct.pack(">BH", STATUS_BYTE[record.status], len(call_id)) + call_id + record.payload.encode()
    return struct.pack(">I", len(body)) + body


def read_back(path) -> list[Record]:
    log = CallLog(path)
    try:
        return log.records()
    finally:
        log.close()


@pytest.mark.skip("Part 2")
def test_call_log(tmp_path) -> None:
    """In-flight calls survive a crash: the log reads back exactly, and only unanswered calls run again."""
    path = tmp_path / "calls.log"
    zurich = ToolCall("call_A", "get_weather", {"city": "Zurich"})
    tokyo = ToolCall("call_B", "get_weather", {"city": "Tokyo", "units": "°C"})
    bengaluru = ToolCall("call_C", "get_weather", {"city": "Bengaluru"})
    report = "Föhn over Zürich,\nthen rain 🌧\r\n"
    written = [started(zurich), started(bengaluru), done("call_A", report), started(tokyo)]

    log = CallLog(path)
    for record in written:
        log.append(record)
    assert path.read_bytes() == b"".join(frame(r) for r in written), (
        "each record is in the file, in the documented layout, as soon as append returns"
    )
    with pytest.raises(ValueError):
        log.append(done("call_A", "a second answer"))
    with pytest.raises(ValueError):
        log.append(started(zurich))
    with pytest.raises(ValueError):
        log.append(done("call_Z", "an answer to a call that never started"))
    with pytest.raises(ValueError):
        log.append(Record("call_B", "running", ""))
    log.close()

    reopened = CallLog(path)
    assert reopened.records() == written, "the log reads back exactly after a reopen"
    assert reopened.in_flight() == [started(bengaluru), started(tokyo)], (
        "calls without an answer are in flight, in log order"
    )
    with pytest.raises(ValueError):
        reopened.append(done("call_A", "a second answer"))
    weather = WeatherAPI()
    messages = asyncio.run(resume(reopened, {"get_weather": weather}))
    assert sorted(weather.cities()) == ["Bengaluru", "Tokyo"], "only calls without an answer run again, once each"
    reopened.close()
    records = read_back(path)
    assert records[:4] == written and sorted(records[4:], key=lambda r: r.call_id) == [
        done(m["tool_call_id"], m["content"]) for m in sorted(messages, key=lambda m: m["tool_call_id"])
    ], "resumed answers are logged as done records"

    intact, kept = path.read_bytes(), records
    log = CallLog(path)
    assert log.in_flight() == [], "nothing is in flight once every call has an answer"
    log.append(started(ToolCall("call_D", "get_weather", {"city": "Zurich", "units": "°C"})))
    log.close()
    full = path.read_bytes()
    lima = started(ToolCall("call_E", "get_weather", {"city": "Lima"}))
    for cut in (5, 9, len(full) - len(intact) - 1, 4, 3, 1):
        path.write_bytes(full[: len(intact) + cut])  # the host died in the middle of an append
        log = CallLog(path)
        assert log.records() == kept, f"a torn last record is dropped and the ones before it kept (cut {cut})"
        log.append(lima)
        log.close()
        assert read_back(path) == kept + [lima], "records appended after a torn one read back"


CITIES = [PlannedCall("bengaluru", 400), PlannedCall("tokyo", 600), PlannedCall("zurich", 800)]


def timeline(plan: Plan) -> dict:
    return {cid: (slot.start_ms, slot.end_ms) for cid, slot in plan.slots.items()}


@pytest.mark.skip("Part 3")
def test_plan_fanout() -> None:
    """Simulate a turn: dependencies, a concurrency limit, failures and the wall clock."""
    plan = plan_fanout(CITIES, limit=3)
    assert (plan.wall_ms, plan.serial_ms) == (800, 1800), (
        "in parallel a turn costs its slowest call, in series the sum"
    )
    assert plan.slots["zurich"] == Slot("ok", 0, 800), "a call that runs has a start and an end"
    assert plan_fanout(CITIES, limit=1).wall_ms == 1800, "a limit of one runs the calls one after another"
    assert timeline(plan_fanout(CITIES, limit=2)) == {
        "bengaluru": (0, 400),
        "tokyo": (0, 600),
        "zurich": (400, 1200),
    }, "at most `limit` calls run at once, and a freed slot is taken at once"
    assert plan_fanout([], limit=3) == Plan({}, 0, 0), "an empty turn takes no time"

    summary = [*CITIES, PlannedCall("summary", 30, after=("bengaluru", "tokyo", "zurich"))]
    assert plan_fanout(summary, limit=3).slots["summary"] == Slot("ok", 800, 830), (
        "a call waits for every one of its dependencies"
    )

    files = [
        PlannedCall("write_file", 50, after=("create_file",)),
        PlannedCall("bengaluru", 400),
        PlannedCall("create_file", 100),
        PlannedCall("tokyo", 600),
    ]
    plan = plan_fanout(files, limit=2)
    assert timeline(plan) == {
        "write_file": (400, 450),
        "bengaluru": (0, 400),
        "create_file": (0, 100),
        "tokyo": (100, 700),
    }, "waiting calls start first come, first served"
    assert list(plan.slots) == ["write_file", "bengaluru", "create_file", "tokyo"], "slots are listed in declaration order"
    assert (plan.wall_ms, plan.serial_ms) == (700, 1150), "the turn ends with its last call"

    ties = [
        PlannedCall("a", 100),
        PlannedCall("b", 100),
        PlannedCall("slow", 300),
        PlannedCall("after_b", 10, after=("b",)),
        PlannedCall("after_a", 10, after=("a",)),
    ]
    assert timeline(plan_fanout(ties, limit=2)) == {
        "a": (0, 100),
        "b": (0, 100),
        "slow": (100, 400),
        "after_b": (100, 110),
        "after_a": (110, 120),
    }, "calls that become ready at the same moment queue in declaration order"

    broken = [
        PlannedCall("create_file", 100, fails=True),
        PlannedCall("write_file", 50, after=("create_file",)),
        PlannedCall("tokyo", 600),
        PlannedCall("bengaluru", 400),
    ]
    plan = plan_fanout(broken, limit=2)
    assert {cid: slot.status for cid, slot in plan.slots.items()} == {
        "create_file": "failed",
        "write_file": "skipped",
        "tokyo": "ok",
        "bengaluru": "ok",
    }, "a call whose dependency failed is skipped"
    assert plan.slots["write_file"] == Slot("skipped", None, None), "a skipped call never runs"
    assert plan.slots["bengaluru"] == Slot("ok", 100, 500), "a skipped call takes no slot"
    assert (plan.wall_ms, plan.serial_ms) == (600, 1100), (
        "every call that runs counts, failed ones too; skipped calls cost nothing"
    )
    chain = [
        PlannedCall("notify", 5, after=("upload",)),
        PlannedCall("upload", 200, after=("zip",)),
        PlannedCall("zip", 300, fails=True),
    ]
    plan = plan_fanout(chain, limit=2)
    assert {cid: slot.status for cid, slot in plan.slots.items()} == {
        "notify": "skipped",
        "upload": "skipped",
        "zip": "failed",
    }, "a failure skips everything downstream of it, however far"
    assert (plan.wall_ms, plan.serial_ms) == (300, 300), "a failed call still takes its time"

    with pytest.raises(ValueError):
        plan_fanout([PlannedCall("write_file", 50, after=("create_flie",))], limit=2)
    with pytest.raises(ValueError):
        plan_fanout([PlannedCall("a", 10, after=("b",)), PlannedCall("b", 10, after=("a",))], limit=2)
    with pytest.raises(ValueError):  # a cycle behind a failing call is still a cycle
        plan_fanout(
            [
                PlannedCall("create_file", 100, fails=True),
                PlannedCall("write_file", 50, after=("create_file", "read_file")),
                PlannedCall("read_file", 30, after=("write_file",)),
            ],
            limit=2,
        )
    with pytest.raises(ValueError):
        plan_fanout([PlannedCall("a", 10), PlannedCall("a", 20)], limit=2)
    with pytest.raises(ValueError):
        plan_fanout(CITIES, limit=0)


def ndjson(chunks: list[str]) -> list[dict]:
    return [json.loads(line) for line in "".join(chunks).splitlines()]


@pytest.mark.skip("Part 4")
def test_stream_results() -> None:
    """Each call runs at its call_stop, and its line goes out while the model is still writing the turn."""

    async def first_line_while_streaming() -> tuple[list[str], bool]:
        shown = asyncio.Event()
        held_up = []

        async def model():
            yield start(0, "call_A")
            yield delta(0, '{"city": "Tokyo"}')
            yield stop(0)
            yield start(1, "call_B")
            yield delta(1, '{"city": ')
            try:  # still writing call_B: wait until call_A's line is out
                await asyncio.wait_for(shown.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                held_up.append(True)
            yield delta(1, '"Zurich"}')
            yield stop(1)
            yield finish("tool_calls")

        chunks = []
        async for chunk in stream_results(model(), {"get_weather": WeatherAPI()}):
            chunks.append(chunk)
            shown.set()
        return chunks, bool(held_up)

    chunks, held_up = asyncio.run(first_line_while_streaming())
    assert not held_up, "write each line as soon as it is known, while the model is still streaming"
    assert [line["tool_call_id"] for line in ndjson(chunks)] == ["call_A", "call_B"], (
        "every call that runs gets a line"
    )

    turn = [
        start(0, "call_A"),
        start(1, "call_B"),
        delta(0, '{"city": "Zur'),
        delta(1, '{"city": "Li'),
        delta(0, 'ich"}'),
        stop(0),
        cancel(1),
        start(2, "call_C"),
        delta(2, '{"city": "Atlantis"}'),
        stop(2),
        start(3, "call_D"),
        delta(3, '{"city": "Bengaluru"}'),
        start(4, "call_E"),
        delta(4, '{"city": "To'),
    ]

    async def cut_off():
        async for event in replay(turn):
            yield event
        await asyncio.sleep(0.03)  # the model hits its output limit a moment later
        yield finish("length")

    async def collect(weather: WeatherAPI) -> list[str]:
        return [chunk async for chunk in stream_results(cut_off(), {"get_weather": weather})]

    weather = WeatherAPI()
    assert ndjson(asyncio.run(collect(weather))) == [
        {"tool_call_id": "call_B", "name": "get_weather", "status": "cancelled"},
        {
            "tool_call_id": "call_C",
            "name": "get_weather",
            "status": "error",
            "error": "LookupError: no weather station in Atlantis",
        },
        {"tool_call_id": "call_D", "name": "get_weather", "status": "incomplete"},
        {"tool_call_id": "call_E", "name": "get_weather", "status": "incomplete"},
        {"tool_call_id": "call_A", "name": "get_weather", "status": "ok", "content": {"city": "Zurich", "temp_c": 4}},
    ], "one line per call, in the order each outcome becomes known"
    assert weather.cities() == ["Zurich", "Atlantis"], "cancelled and incomplete calls never run"


TRICKY = [
    '{"q": "a}b{c"}',
    '{"say": "a\\"}b", "n": [1, {"m": "\\\\"}]}',
    '{"path": "C:\\\\", "say": "\\"hi\\"", "n": 12}',
    '{"ci\\u0074y": "Z\\u00fcrich", "sky": "\\ud83c\\udf27", "ok": true, "none": null}',
    '{"cities": ["Bengaluru", {"name": "Tokyo", "tags": [",", ":", "]}"]}], "units": "metric", "n": -1.5e3}',
    " { } ",
    '{"a": {}, "b": [], "c": [[], {"d": 0}]}\n',
]


@pytest.mark.skip("Part 5")
def test_partial_arguments() -> None:
    """Follow arguments as they stream: is the object complete yet, and which members are final?"""
    args = PartialArguments()
    args.feed('{"q": "a}b')
    assert not args.complete, "a brace inside a string closes nothing"
    args.feed('"}')
    assert args.complete and args.members == {"q": "a}b"}, "the object is complete at its closing brace"

    args = PartialArguments()
    args.feed('{"city": "Zurich", "units": "metr')
    assert args.members == {"city": "Zurich"} and not args.complete, (
        "a member is final once the comma after it arrives"
    )

    args, seen = PartialArguments(), []
    for chunk in ('{"path": "C:\\', '\\", "say": "\\', '"hi\\"", "n": 1', "2}"):
        args.feed(chunk)
        seen.append((dict(args.members), args.complete))
    assert seen == [
        ({}, False),
        ({"path": "C:\\"}, False),
        ({"path": "C:\\", "say": '"hi"'}, False),
        ({"path": "C:\\", "say": '"hi"', "n": 12}, True),
    ], "an escape can be split between chunks, and a number can still grow"

    rng = random.Random(7)
    for text in TRICKY:
        final = json.loads(text)
        end = len(text.rstrip())  # the closing brace is character end - 1
        splits = [list(range(1, len(text)))]
        for _ in range(25):
            splits.append(sorted(rng.sample(range(1, len(text)), rng.randint(1, min(8, len(text) - 1)))))
        for cuts in splits:
            args = PartialArguments()
            for a, b in zip([0, *cuts], [*cuts, len(text)]):
                args.feed(text[a:b])
                assert args.complete == (b >= end), f"complete exactly when the closing brace arrives: {text!r}"
                assert set(args.members) <= set(final) and all(
                    final[key] == value for key, value in args.members.items()
                ), f"members hold only final values: {text!r}"
            assert args.members == final, f"every member is there at the end: {text!r}"

    with pytest.raises(ValueError):
        PartialArguments().feed('["Tokyo", "Zurich"]')
    args = PartialArguments()
    args.feed('{"cities": ["Tokyo", "Zurich"')
    with pytest.raises(ValueError):
        args.feed("}")
    args = PartialArguments()
    args.feed('{"city": "Oslo"}  \n')
    assert args.complete
    with pytest.raises(ValueError):
        args.feed('{"city": "Lima"}')
    args = PartialArguments()
    args.feed('{"city": "Oslo",')
    with pytest.raises(ValueError):
        args.feed("}")
    args = PartialArguments()
    with pytest.raises(ValueError):  # by the comma that ends the broken member, not at the closing brace
        for chunk in ('{"city" "Oslo"', ', "units": "metr'):
            args.feed(chunk)
