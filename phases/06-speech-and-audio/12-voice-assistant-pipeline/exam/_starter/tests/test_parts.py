import asyncio
import json
import random
import time

import pytest
from voicebot.agent import FALLBACK, respond, speakable
from voicebot.schema import validate
from voicebot.service import VoiceBot
from voicebot.sessions import SessionStore
from voicebot.tools import Timers, ToolBox, calendar_tool, timer_tool, weather_tool
from voicebot.trace import turn_reports


def call(call_id: str, name: str, **arguments) -> dict:
    return {"id": call_id, "name": name, "arguments": arguments}


def asks(*calls: dict) -> dict:
    """An assistant message that calls tools."""
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def says(text: str) -> dict:
    return {"role": "assistant", "content": text}


def scripted(*replies: dict):
    """A stand-in LLM that returns the given replies in order; the last one repeats."""
    requests: list[list[dict]] = []

    async def llm(messages: list[dict], tools: list[dict]) -> dict:
        assert isinstance(tools, list) and tools, "every LLM request offers the tool specs"
        requests.append(list(messages))
        return replies[min(len(requests), len(replies)) - 1]

    llm.requests = requests
    return llm


def answered(messages: list[dict]) -> bool:
    """Every tool call is answered by one tool message before the next assistant message."""
    open_calls: list[str] = []
    for message in messages:
        if message["role"] == "assistant":
            if open_calls:
                return False
            open_calls = [c["id"] for c in message.get("tool_calls") or []]
        elif message["role"] == "tool":
            if message["tool_call_id"] not in open_calls:
                return False
            open_calls.remove(message["tool_call_id"])
    return not open_calls


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


def server_sent_events(text: str) -> list[tuple[str, dict]]:
    """Parse a text/event-stream body: blocks of "field: value" lines, each block ending in a blank line."""
    assert text.endswith("\n\n"), "every server-sent event ends with a blank line"
    events = []
    for block in text[:-2].split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((fields["event"], json.loads(fields["data"])))
    return events


FORECASTS = {"Tromsø": {"temp_c": -5, "summary": "light snow"}}


@pytest.mark.skip("Part 1")
def test_tool_dispatch() -> None:
    """Tool calls run in either provider format, and every problem goes back to the LLM."""
    timers = Timers(clock=lambda: 1000.0)

    def fetch_weather(city: str) -> dict:
        """A blocking HTTP client: slow, and down for cities it does not know."""
        if city not in FORECASTS:
            raise ConnectionError("weather service unreachable")
        time.sleep(2.0)
        return FORECASTS[city]

    async def fetch_calendar() -> dict:
        await asyncio.sleep(0)
        return {"title": "Dentist", "starts": "2026-11-02T09:30"}

    box = ToolBox([timer_tool(timers), weather_tool(fetch_weather), calendar_tool(fetch_calendar)])

    def run(tool_call: dict) -> dict:
        message = asyncio.run(box.dispatch(tool_call))
        assert message["role"] == "tool" and message["tool_call_id"] == tool_call["id"], (
            "answer each call with a tool message that carries its id"
        )
        return json.loads(message["content"])

    assert run(call("c1", "set_timer", seconds=300, label="tea")) == {
        "ok": True,
        "result": {"timer_id": "t1", "label": "tea", "fires_at": 1300.0},
    }
    assert run({"id": "c2", "name": "set_timer", "arguments": '{"seconds": 60}'}) == {
        "ok": True,
        "result": {"timer_id": "t2", "label": "", "fires_at": 1060.0},
    }, "OpenAI-style providers send the arguments as JSON text"

    unknown = run(call("c3", "set_alarm", time="7am"))
    assert unknown["ok"] is False and "set_timer" in unknown["error"], (
        "an unknown tool comes back as an error that lists the real tools"
    )
    assert run({"id": "c4", "name": "set_timer", "arguments": '{"seconds": 6'})["ok"] is False, (
        "broken JSON comes back as an error"
    )
    misnamed = run(call("c5", "set_timer", minutes=5))
    assert "minutes" in misnamed["error"] and "seconds" in misnamed["error"], (
        "name the unknown parameter and the expected one"
    )
    quoted = run(call("c6", "set_timer", seconds="300"))
    assert quoted["ok"] is False and "seconds" in quoted["error"], (
        "a wrongly typed argument is rejected by name before the tool runs"
    )
    assert [t["timer_id"] for t in timers.pending()] == ["t2", "t1"], "rejected calls start no timer"

    async def weather_while_listening() -> tuple[dict, float]:
        gaps: list[float] = []
        last = time.perf_counter()

        async def microphone() -> None:  # the same event loop reads audio and runs VAD
            nonlocal last
            while True:
                await asyncio.sleep(0.001)
                now = time.perf_counter()
                gaps.append(now - last)
                last = now

        mic = asyncio.create_task(microphone())
        await asyncio.sleep(0.01)
        message = await box.dispatch(call("c7", "get_weather", city="Tromsø"))
        gaps.append(time.perf_counter() - last)
        mic.cancel()
        return json.loads(message["content"]), max(gaps)

    weather, stall = asyncio.run(weather_while_listening())
    assert weather == {"ok": True, "result": {"city": "Tromsø", "temp_c": -5, "summary": "light snow"}}
    assert stall < 0.2, "a slow tool must not block the event loop"

    assert run({"id": "c8", "name": "next_event", "arguments": ""}) == {
        "ok": True,
        "result": {"title": "Dentist", "starts": "2026-11-02T09:30"},
    }, "async tools are awaited"
    down = run(call("c9", "get_weather", city="Atlantis"))
    assert down["ok"] is False and "weather service unreachable" in down["error"], (
        "a failing tool comes back as an error result"
    )


TURN = [
    {"role": "user", "content": "Start a tea timer and remind me to call Dr. Okafor in Zürich 🍵"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "call_1", "name": "set_timer", "arguments": '{"seconds":300,"label":"tea"}'},
            {"id": "toolu_2", "name": "add_reminder", "arguments": {"text": "Call Dr. Okafor", "at": None}},
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": '{"ok": true, "result": {"timer_id": "t1"}}'},
    {
        "role": "tool",
        "tool_call_id": "toolu_2",
        "content": '{"ok": false, "error": "TimeoutError: calendar"}',
        "is_error": True,
    },
    {"role": "assistant", "content": "Your tea timer is on. I couldn't save the reminder."},
]


@pytest.mark.skip("Part 2")
def test_session_store(tmp_path) -> None:
    """Conversations round-trip exactly, expire when idle, and deleted transcripts are gone."""
    path = tmp_path / "sessions.sqlite3"
    store = SessionStore(str(path), ttl_s=600)
    for message in TURN:
        store.append("kitchen", message, now=1000.0)
    store.append("car", {"role": "user", "content": "Navigate to 221B Baker Street"}, now=1000.0)
    store.append("car", {"role": "assistant", "content": "Starting the route to Baker Street."}, now=1000.0)
    assert store.history("kitchen", now=1000.0) == TURN, "a turn round-trips exactly, in order"
    assert store.history("garage", now=1000.0) == [], "an unknown session has no history"
    with pytest.raises(ValueError):
        store.append("kitchen", {"role": "robot", "content": "beep"}, now=1000.0)
    store.close()

    store = SessionStore(str(path), ttl_s=600)
    assert store.history("kitchen", now=1599.0) == TURN, "a reopened store sees earlier sessions"
    follow_up = {"role": "user", "content": "Make it six minutes"}
    store.append("kitchen", follow_up, now=1599.0)
    assert store.history("car", now=1600.0) == [], "a session expires ttl_s after its last message"
    assert store.history("kitchen", now=2100.0) == TURN + [follow_up], "a session in use stays alive"
    home = {"role": "user", "content": "Navigate home"}
    store.append("car", home, now=2100.0)
    assert store.history("car", now=2100.0) == [home], "an expired session starts over"
    assert b"Baker" not in path.read_bytes(), "deleted transcripts must not stay readable in the database file"
    assert store.purge(now=2200.0) == 6, "purge deletes every expired session"
    assert store.history("car", now=2200.0) == [home]
    store.close()
    stored = path.read_bytes()
    assert b"Okafor" not in stored and b"Baker" not in stored, (
        "deleted transcripts must not stay readable in the database file"
    )


@pytest.mark.skip("Part 3")
def test_voice_tool_loop() -> None:
    """Tool results go back to the LLM until it answers, within limits, in words a TTS can read."""
    assert speakable("I set two timers:\n1. `pasta`, 10 minutes\n2. *eggs*, 7 minutes") == (
        "I set two timers: pasta, 10 minutes. eggs, 7 minutes."
    ), "list items become sentences and markdown is dropped"
    assert speakable("-3°C and clear.\n2.5 m/s winds from the north.") == (
        "-3°C and clear. 2.5 m/s winds from the north."
    ), "a minus sign or a decimal is not a list marker"

    timers = Timers(clock=lambda: 1000.0)

    def fetch_weather(city: str) -> dict:
        if city != "Oslo":
            raise ConnectionError("weather service unreachable")
        return {"temp_c": -5, "summary": "light snow"}

    box = ToolBox([timer_tool(timers), weather_tool(fetch_weather)])
    question = {"role": "user", "content": "How cold is it in Oslo? And start a pasta timer."}

    final = says(
        "## Oslo right now\n- **-5°C**, light snow\n- Feels like -9°C\n\n"
        "Pasta timer set. More at [yr.no](https://www.yr.no/en)."
    )
    llm = scripted(
        asks(call("c1", "get_weather", city="Oslo"), call("c2", "set_timer", seconds=600, label="pasta")),
        final,
    )
    messages = [question]
    spoken = asyncio.run(respond(llm, box, messages))
    assert len(llm.requests) == 2 and llm.requests[1] == messages[:4], "tool results go back to the LLM"
    assert [m.get("tool_call_id") for m in messages[2:4]] == ["c1", "c2"], "every call is answered, in order"
    assert messages[4:] == [final], "the history keeps the LLM's own reply"
    assert spoken == "Oslo right now. -5°C, light snow. Feels like -9°C. Pasta timer set. More at yr.no.", (
        "speak the final answer as plain sentences"
    )

    flaky = scripted(
        asks(call("w1", "get_weather", city="Atlantis"), call("p1", "set_timer", minutes=10)),
        asks(call("w2", "get_weather", city="Atlantis")),
        says("It is sunny in Atlantis."),
    )
    messages = [question]
    assert asyncio.run(respond(flaky, box, messages)) == FALLBACK, "a tool that fails twice ends the turn"
    assert len(flaky.requests) == 2, "a failed tool gets one retry"
    assert messages[-1] == {"role": "assistant", "content": FALLBACK}, "the fallback is what the assistant said"

    looping = scripted(*(asks(call(f"s{i}", "set_timer", seconds=60)) for i in (1, 2, 3)), says("Done."))
    messages = [question]
    assert asyncio.run(respond(looping, box, messages, max_steps=3)) == FALLBACK, "stop after max_steps LLM calls"
    assert len(looping.requests) == 3, "the LLM is called at most max_steps times"
    assert answered(messages) and messages[-2]["tool_call_id"] == "s3", (
        "every tool call is answered, even the ones that were not run"
    )
    assert len(timers.pending()) == 3, "calls in the last allowed reply are not run"

    store = SessionStore(ttl_s=600)
    bot = VoiceBot(
        scripted(
            asks(call("a1", "set_timer", minutes=5)),
            asks(call("a2", "set_timer", seconds=300)),
            says("**Done.** Your timer is set for *five minutes*."),
        ),
        box,
        store,
        max_steps=3,
    )
    assert asyncio.run(bot.handle("kitchen", "set a five minute timer", now=1000.0)) == (
        "Done. Your timer is set for five minutes."
    ), "a misnamed argument, one retry, then a spoken confirmation"
    saved = store.history("kitchen", now=1000.0)
    assert [m["role"] for m in saved] == ["user", "assistant", "tool", "assistant", "tool", "assistant"]
    assert answered(saved) and any(t["fires_at"] == 1300.0 for t in timers.pending()), (
        "the whole exchange is saved and the timer is running"
    )


TRACE = [
    {"ms": 0, "turn": 1, "type": "vad.start"},
    {"ms": 400, "turn": 1, "type": "stt.partial", "text": "what's the"},
    {"ms": 1100, "turn": 1, "type": "vad.end"},
    {"ms": 1180, "turn": 1, "type": "stt.final", "text": "what's the weather in Oslo"},
    {"ms": 1350, "turn": 1, "type": "llm.token", "text": "It's"},
    {"ms": 1520, "turn": 1, "type": "tts.audio"},
    {"ms": 1720, "turn": 1, "type": "tts.audio"},
    {"ms": 1920, "turn": 1, "type": "tts.audio"},
    {"ms": 3000, "turn": 1, "type": "turn.end"},
    {"ms": 3400, "turn": 2, "type": "stt.partial", "text": "Thanks"},
    {"ms": 3450, "turn": 2, "type": "stt.final", "text": "Thanks for watching!"},
    {"ms": 3600, "turn": 2, "type": "llm.token", "text": "You're"},
    {"ms": 3800, "turn": 2, "type": "tts.audio"},
    {"ms": 4300, "turn": 2, "type": "turn.end"},
    {"ms": 5000, "turn": 3, "type": "vad.start"},
    {"ms": 5600, "turn": 3, "type": "vad.end"},
    {"ms": 5700, "turn": 3, "type": "stt.final", "text": "read me my messages"},
    {"ms": 5850, "turn": 3, "type": "llm.token", "text": "You"},
    {"ms": 6250, "turn": 3, "type": "tts.audio"},
    {"ms": 6450, "turn": 3, "type": "tts.audio"},
    {"ms": 6600, "turn": 3, "type": "user.barge_in"},
    {"ms": 6600, "turn": 4, "type": "vad.start"},
    {"ms": 6700, "turn": 3, "type": "turn.end"},
    {"ms": 7400, "turn": 4, "type": "vad.end"},
    {"ms": 7500, "turn": 4, "type": "stt.final", "text": "actually, what's on my calendar"},
    {"ms": 7650, "turn": 4, "type": "llm.token", "text": "At"},
    {"ms": 8100, "turn": 4, "type": "tts.audio"},
    {"ms": 8300, "turn": 4, "type": "tts.audio"},
    {"ms": 9000, "turn": 4, "type": "user.barge_in"},
    {"ms": 9000, "turn": 5, "type": "vad.start"},
    {"ms": 9100, "turn": 4, "type": "tts.audio"},
    {"ms": 9300, "turn": 4, "type": "llm.token", "text": "and"},
    {"ms": 9500, "turn": 4, "type": "tts.audio"},
    {"ms": 9600, "turn": 5, "type": "vad.end"},
    {"ms": 9700, "turn": 5, "type": "stt.final", "text": "Thank you."},
    {"ms": 9900, "turn": 4, "type": "tts.audio"},
    {"ms": 9950, "turn": 4, "type": "turn.end"},
    {"ms": 10150, "turn": 5, "type": "tts.audio"},
    {"ms": 10350, "turn": 5, "type": "tts.audio"},
    {"ms": 10800, "turn": 5, "type": "turn.end"},
]

REPORTS = [
    ("turn", {"turn": 1, "text": "what's the weather in Oslo", "first_audio_ms": 420, "barge_in_ms": None}),
    ("hallucination", {"turn": 2, "text": "Thanks for watching!"}),
    ("turn", {"turn": 3, "text": "read me my messages", "first_audio_ms": 650, "barge_in_ms": 0}),
    ("turn", {"turn": 4, "text": "actually, what's on my calendar", "first_audio_ms": 700, "barge_in_ms": 900}),
    ("turn", {"turn": 5, "text": "Thank you.", "first_audio_ms": 550, "barge_in_ms": None}),
]


@pytest.mark.skip("Part 4")
def test_turn_reports() -> None:
    """Turn latencies come from event times, whatever order the events arrive in."""

    async def replay(events: list[dict]):
        for event in events:
            yield event

    def reports(events: list[dict]) -> list[tuple[str, dict]]:
        return server_sent_events("".join(collect(turn_reports(replay(events), max_delay_ms=300))))

    in_order = reports(TRACE)
    assert in_order[1] == REPORTS[1], "a turn the user never spoke is a silence hallucination"
    assert in_order[4][0] == "turn", "real speech is a turn, whatever it says"
    assert in_order == REPORTS, "first audio is timed from vad.end, talk-over from the barge-in"

    jitter = random.Random(7)
    shuffled = [jitter.randrange(300) for _ in TRACE]
    late = {("tts.audio", 1520), ("user.barge_in", 6600), ("tts.audio", 9900)}
    stragglers = [299 if (e["type"], e["ms"]) in late else 0 for e in TRACE]
    for delays in (shuffled, stragglers):
        order = sorted(range(len(TRACE)), key=lambda i: (TRACE[i]["ms"] + delays[i], i))
        assert reports([TRACE[i] for i in order]) == REPORTS, "same reports whatever the arrival order"

    pulled: list[int] = []

    async def live():
        for i, event in enumerate(TRACE):
            pulled.append(i)
            yield event

    async def first_report() -> str:
        agen = turn_reports(live(), max_delay_ms=300)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert server_sent_events(asyncio.run(first_report())) == REPORTS[:1]
    assert len(pulled) <= 10, "report each turn as soon as it is complete"


STEP = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["say", "set_timer", "play", "group"]},
        "text": {"type": "string"},
        "seconds": {"type": "integer"},
        "playlist_id": {"type": "string"},
        "steps": {"type": "array", "items": {"$ref": "#/$defs/step"}},
    },
    "required": ["action"],
    "additionalProperties": False,
}

ROUTINE = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "trigger": {
            "type": "object",
            "properties": {
                "kind": {"enum": ["time", "phrase"]},
                "at": {"type": ["string", "null"]},
                "phrase": {"type": ["string", "null"]},
            },
            "required": ["kind"],
            "additionalProperties": False,
        },
        "steps": {"type": "array", "items": {"$ref": "#/$defs/step"}},
    },
    "required": ["name", "trigger", "steps"],
    "additionalProperties": False,
    "$defs": {"step": STEP},
}


@pytest.mark.skip("Part 5")
def test_argument_schema() -> None:
    """Every problem in nested tool arguments is reported, each at its JSON pointer."""
    good = {
        "name": "Good night",
        "trigger": {"kind": "phrase", "phrase": "good night"},
        "steps": [{"action": "group", "steps": [{"action": "say", "text": "Sleep well"}]}],
    }
    assert validate(ROUTINE, good) == [], "valid arguments have no problems"
    assert validate(ROUTINE, ["Morning"]) == [("", "type")], "the root's pointer is the empty string"

    from_the_llm = {
        "name": "Morning",
        "trigger": {"kind": "time", "at": None, "on/off": True},
        "steps": [
            {"action": "say", "text": "Good morning"},
            {"action": "speak", "text": "Here is the weather"},
            {
                "action": "group",
                "steps": [
                    {"action": "set_timer", "seconds": "600"},
                    {"action": "set_timer", "seconds": True},
                    {"text": "Coffee is ready"},
                ],
            },
            {"action": "play", "playlist": "Morning jazz"},
        ],
    }
    assert sorted(validate(ROUTINE, from_the_llm)) == [
        ("/steps/1/action", "enum"),
        ("/steps/2/steps/0/seconds", "type"),
        ("/steps/2/steps/1/seconds", "type"),
        ("/steps/2/steps/2/action", "missing"),
        ("/steps/3/playlist", "unexpected"),
        ("/trigger/on~1off", "unexpected"),
    ], "report every problem, at its path"
    assert sorted(validate(ROUTINE, {"name": "Night", "trigger": "at 10pm", "steps": "lights off"})) == [
        ("/steps", "type"),
        ("/trigger", "type"),
    ], "nothing below a value of the wrong type is checked"

    open_object = {"type": "object", "properties": {"a/b": {"type": "integer"}, "m~n": {"type": "integer"}}}
    assert sorted(validate(open_object, {"a/b": "1", "m~n": "2"})) == [("/a~1b", "type"), ("/m~0n", "type")], (
        "a pointer writes '/' as ~1 and '~' as ~0"
    )
    assert validate(open_object, {"a/b": 1, "volume": 3}) == [], (
        "without additionalProperties: false, other properties are allowed"
    )
