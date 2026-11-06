import asyncio
import re
import time

import pytest
from voiceframe.budget import grade, latency
from voiceframe.frames import DOWNSTREAM, UPSTREAM, Frame
from voiceframe.metrics import FrameEvent, expose_metrics
from voiceframe.pipeline import build_pipeline
from voiceframe.recording import Record, Recorder, read_recording
from voiceframe.turns import REPEAT_PROMPT, TurnTaker


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


REPLIES = {
    "hello": "hi there, how can I help today?",
    "read me the terms": " ".join(f"clause{i}" for i in range(400)),
    "refund please": "sure, I can help with a refund; what order number should I look up?",
    "and the fees": "there is no fee for a refund within thirty days.",
}


@pytest.mark.skip("Part 1")
def test_barge_in() -> None:
    """Barge-in cuts the bot off mid-utterance, and the LLM remembers only what the user heard."""
    played: list[str] = []
    played_at: list[float] = []
    barge = {"after_word": 0, "while_synthesizing": ""}

    def model(messages: list[dict]) -> str:
        return REPLIES[messages[-1]["content"]]

    def synthesize(word: str) -> bytes:
        time.sleep(0.002)  # a fast TTS still takes a moment per word
        if word == barge["while_synthesizing"]:
            pipe.transport.barge_in()  # the user starts talking while this word is synthesized
        return word.encode()

    def play(audio: bytes) -> None:
        played.append(audio.decode())
        played_at.append(time.perf_counter())
        if len(played) == barge["after_word"]:
            pipe.transport.barge_in()  # the user starts talking right after this word

    pipe = build_pipeline(model, synthesize, play)

    pipe.hear("hello")
    assert played == REPLIES["hello"].split(), "a turn nobody interrupts is spoken in full"
    pipe.hear("   ")
    assert len(played) == 7 and len(pipe.llm.context) == 2, "silence is not speech"

    played.clear()
    played_at.clear()
    barge["after_word"] = 1
    start = time.perf_counter()
    pipe.hear("read me the terms")
    assert played_at and played_at[0] - start < 0.08, (
        "the first word should play before the rest of the reply is synthesized"
    )
    assert played == ["clause0"], "barge-in stops the bot mid-utterance"

    played.clear()
    barge["after_word"] = 3
    pipe.hear("refund please")
    assert played == ["sure,", "I", "can"], "barge-in stops the bot mid-utterance"
    assert pipe.llm.context == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there, how can I help today?"},
        {"role": "user", "content": "read me the terms"},
        {"role": "assistant", "content": "clause0"},
        {"role": "user", "content": "refund please"},
        {"role": "assistant", "content": "sure, I can"},
    ], "the LLM remembers only what the user heard"

    played.clear()
    barge["after_word"] = 0
    barge["while_synthesizing"] = "is"
    pipe.hear("and the fees")
    assert played == ["there"], "a word synthesized after the cancel is never played"
    assert pipe.llm.context[-1] == {"role": "assistant", "content": "there"}, (
        "the LLM remembers only what the user heard"
    )

    played.clear()
    barge["while_synthesizing"] = ""
    pipe.hear("hello")
    assert played == REPLIES["hello"].split(), "the next turn is spoken in full"
    pipe.transport.barge_in()  # the user starts talking just after the bot is done
    assert pipe.llm.context[-1] == {"role": "assistant", "content": REPLIES["hello"]}, (
        "a reply the user heard in full stays whole"
    )
    assert [m["role"] for m in pipe.llm.context] == ["user", "assistant"] * 5, (
        "the context alternates user and assistant"
    )


@pytest.mark.skip("Part 2")
def test_call_recording(tmp_path) -> None:
    """A call recording reads back exactly, survives a reopen, and survives a crash mid-write."""
    path = tmp_path / "call.vfr"
    pcm = bytes(range(256)) * 4 + b"\n\r\n\x00"
    records = [
        Record(1_730_000_000_123_456_789, DOWNSTREAM, "audio_chunk", pcm),
        Record(1_730_000_000_123_456_790, DOWNSTREAM, "transcript", "¿qué tal? 你好".encode()),
        Record(1_730_000_000_400_000_001, UPSTREAM, "cancel", b""),
        Record(2**63 - 1, DOWNSTREAM, "tts_audio", bytes(70_000)),
    ]

    rec = Recorder(path)
    for r in records[:3]:
        rec.write(r)
    assert read_recording(path) == records[:3], "a recording must read back exactly"
    with pytest.raises(ValueError):
        rec.write(Record(2**63, DOWNSTREAM, "tts_audio", b""))
    with pytest.raises(ValueError):
        rec.write(Record(-1, UPSTREAM, "cancel", b""))
    with pytest.raises(ValueError):
        rec.write(Record(5, "sideways", "cancel", b""))
    rec.close()

    whole = path.stat().st_size
    rec = Recorder(path)
    rec.write(records[3])
    rec.close()
    assert read_recording(path) == records, "a reopened recording keeps every record, in order"

    with open(path, "r+b") as f:  # the process died 1,000 bytes into writing the last record
        f.truncate(whole + 1000)
    assert read_recording(path) == records[:3], "part of a record at the end is left out"

    late = Record(1_730_000_001_000_000_000, DOWNSTREAM, "text", b"still here")
    rec = Recorder(path)
    rec.write(late)
    assert read_recording(path) == records[:3] + [late], (
        "records appended after a crash follow the last whole record"
    )
    rec.close()

    with open(path, "r+b") as f:  # and again, this time 3 bytes into writing the next one
        f.truncate(whole + 3)
    assert read_recording(path) == records[:3], "part of a record at the end is left out"
    rec = Recorder(path)
    rec.write(late)
    rec.close()
    assert read_recording(path) == records[:3] + [late], (
        "records appended after a crash follow the last whole record"
    )

    other = tmp_path / "notes.txt"
    other.write_bytes(b"hello")
    with pytest.raises(ValueError):
        read_recording(other)


@pytest.mark.skip("Part 3")
def test_turn_taking() -> None:
    """End turns on "?" or silence, gate on STT confidence, and drop the bot's stale frames."""
    tt = TurnTaker(threshold=0.6, silence_ms=700)
    assert tt.user_started(0) == []
    assert tt.transcript(400, "  book a table ", 0.9) == []
    assert tt.user_stopped(450) == []
    assert tt.tick(1000) == []
    assert tt.user_started(1100) == []
    assert tt.tick(1200) == [], "the user is speaking again"
    assert tt.transcript(1500, "", 0.1) == []
    assert tt.transcript(1550, "for two", 0.8) == []
    assert tt.user_stopped(1600) == []
    assert tt.tick(2299) == [], "silence counts from when the user stopped speaking"
    assert tt.tick(2300) == [Frame("transcript", "book a table for two", turn=1)], (
        "700 ms of silence ends the turn; empty segments do not count"
    )
    assert tt.tick(5000) == [], "a turn ends once"

    tt.user_started(6000)
    assert tt.transcript(6400, "is eight ok? or", 0.9) == [], "only a question at the end ends the turn"
    assert tt.transcript(6500, "can you do nine? ", 0.95) == [
        Frame("transcript", "is eight ok? or can you do nine?", turn=2)
    ], "a question ends the turn at once"
    tt.user_stopped(6600)
    assert tt.tick(9000) == [], "a turn ends once"

    tt.user_started(10000)
    tt.transcript(10300, "under the name", 0.9)
    tt.transcript(10500, "lou", 0.4)
    tt.transcript(10600, "please", 0.9)
    tt.user_stopped(10700)
    assert tt.tick(11400) == [Frame("text", REPEAT_PROMPT, turn=3)], (
        "the weakest segment decides; the LLM never sees an unsure turn"
    )
    tt.user_started(12000)
    tt.transcript(12300, "lou with", 0.9)
    tt.transcript(12350, "an o u", 0.6)
    tt.user_stopped(12400)
    assert tt.tick(13100) == [Frame("transcript", "lou with an o u", turn=4)], (
        "a confidence equal to the threshold passes"
    )

    assert tt.admit(Frame("tts_audio", b"got", turn=4)), "the reply to the latest turn may start playing"
    tt.bot_started(4)
    assert not tt.admit(Frame("tts_audio", b"late", turn=3)), "frames of an older turn are stale"
    assert tt.user_started(14000) == [Frame("cancel", None, UPSTREAM, turn=4)], (
        "the user talking over the bot cancels the bot's turn"
    )
    assert not tt.admit(Frame("tts_audio", b"it", turn=4)), "nothing of a cancelled turn is played"
    tt.user_stopped(14200)
    assert tt.user_started(14300) == [], "one cancel per bot turn"
    assert tt.transcript(14500, "actually make it three?", 0.9) == [
        Frame("transcript", "actually make it three?", turn=5)
    ]
    tt.user_stopped(14600)
    tt.bot_stopped(4)
    tt.bot_started(5)
    assert tt.admit(Frame("tts_audio", b"three", turn=5)), "a cancel only drops its own turn"
    tt.bot_stopped(5)
    assert tt.user_started(20000) == [], "no cancel while the bot is quiet"


def parse_labels(body: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    i = 0
    while i < len(body):
        m = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)="', body[i:])
        assert m, f"bad label syntax: {body!r}"
        i += m.end()
        value = []
        while body[i] != '"':
            if body[i] == "\\":
                escaped = {"\\": "\\", '"': '"', "n": "\n"}.get(body[i + 1])
                assert escaped is not None, f"label values use the Prometheus escapes only: {body!r}"
                value.append(escaped)
                i += 2
            else:
                value.append(body[i])
                i += 1
        labels[m[1]] = "".join(value)
        i += 1
        if i < len(body):
            assert body[i] == ",", f"bad label syntax: {body!r}"
            i += 1
    return labels


def parse_exposition(text: str) -> tuple[dict[str, str], list[tuple[str, dict, float]]]:
    """A Prometheus text-format reader: # TYPE lines, then name{labels} value samples."""
    assert text.endswith("\n"), "every line of an exposition ends with a newline"
    types: dict[str, str] = {}
    samples: list[tuple[str, dict, float]] = []
    for line in text[:-1].split("\n"):
        if line.startswith("# TYPE "):
            name, kind = line[len("# TYPE ") :].split(" ")
            assert name not in types, "one # TYPE line per metric family"
            assert all(s[0] != name for s in samples), "# TYPE comes before the family's samples"
            types[name] = kind
        elif line.startswith("#") or not line:
            continue
        else:
            m = re.fullmatch(r"([a-zA-Z_:][a-zA-Z0-9_:]*)\{(.*)\} (\S+)", line)
            assert m, f"not a sample line: {line!r}"
            assert m[1] in types, "# TYPE comes before the family's samples"
            assert m[1] == list(types)[-1], "a family's samples follow its own # TYPE line, in one group"
            samples.append((m[1], parse_labels(m[2]), float(m[3])))
    return types, samples


@pytest.mark.skip("Part 4")
def test_metrics_observer() -> None:
    """Frames per stage per window, exposed in the Prometheus text format as each window closes."""
    stages = ["vad", "stt", "llm", 'tts "café"', "out\\sip\n"]  # names as read from a config file
    times = {
        "vad": [0, 20, 40, 999, 1000, 3500],
        "stt": [250, 1250],
        "llm": [1400],
        'tts "café"': [1600, 1700, 3999],
        "out\\sip\n": [],
    }
    data = sorted(
        (FrameEvent(t, stage, DOWNSTREAM) for stage, ts in times.items() for t in ts),
        key=lambda e: e.t_ms,
    )
    # at 1750 ms the user talks over the bot, and the cancel goes UPSTREAM from the transport
    cancel = [FrameEvent(1750, stage, UPSTREAM) for stage in ('tts "café"', "llm", "stt", "vad")]
    events = sorted(data + cancel, key=lambda e: e.t_ms)

    async def feed(items):
        for item in items:
            yield item

    def table(text: str) -> dict:
        types, samples = parse_exposition(text)
        assert types == {"voice_frames_total": "counter", "voice_window_frames": "gauge"}
        for family in types:
            assert [s[1]["stage"] for s in samples if s[0] == family] == stages, (
                "one sample per stage, in pipeline order"
            )
        return {family: [int(s[2]) for s in samples if s[0] == family] for family in types}

    out = collect(expose_metrics(feed(events), stages))
    assert all(isinstance(text, str) for text in out)
    assert out == collect(expose_metrics(feed(data), stages)), (
        "UPSTREAM frames are control, not data, and are not counted"
    )
    assert [table(text) for text in out] == [
        {"voice_frames_total": [4, 1, 0, 0, 0], "voice_window_frames": [4, 1, 0, 0, 0]},
        {"voice_frames_total": [5, 2, 1, 2, 0], "voice_window_frames": [1, 1, 1, 2, 0]},
        {"voice_frames_total": [5, 2, 1, 2, 0], "voice_window_frames": [0, 0, 0, 0, 0]},
        {"voice_frames_total": [6, 2, 1, 3, 0], "voice_window_frames": [1, 0, 0, 1, 0]},
    ], "one exposition per 1 s window of the call, empty windows included"

    late = collect(expose_metrics(feed([FrameEvent(2500, "llm")]), stages))
    assert [table(text)["voice_window_frames"][2] for text in late] == [0, 0, 1], (
        "windows start when the call starts"
    )
    assert collect(expose_metrics(feed([]), stages)) == [], "a call with no frames has no windows"

    pulled: list[int] = []

    async def probe():
        for i in range(100):
            pulled.append(i)
            yield FrameEvent(i * 250, "vad")

    async def first_window() -> str:
        agen = expose_metrics(probe(), stages)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert table(asyncio.run(first_window()))["voice_window_frames"][0] == 4
    assert len(pulled) <= 5, "yield each window as soon as it closes"

    with pytest.raises(ValueError):
        collect(expose_metrics(feed([FrameEvent(0, "asr")]), stages))
    with pytest.raises(ValueError):
        collect(expose_metrics(feed([FrameEvent(0, "asr", UPSTREAM)]), stages))


CASCADE = ["vad", "stt", "llm", "tts", "transport"]


@pytest.mark.skip("Part 5")
def test_latency_budget() -> None:
    """Sum a nested voice chain into a (best, worst) range before shipping it."""
    assert latency(CASCADE) == (400, 990), "a chain adds up"
    assert grade(990) == "common"

    fast = {"stage": "stt", "ms": [100, 250]}
    steady = {"stage": "stt", "ms": [150, 200]}
    assert latency(["vad", {"first": [fast, steady]}, "llm", "tts", "transport"]) == (400, 940), (
        "racing two STTs: whichever finishes first, in the best case and in the worst"
    )
    assert latency(["vad", {"all": [fast, steady]}, "llm", "tts", "transport"]) == (450, 990), (
        "waiting for both STTs: the slower one, in the best case and in the worst"
    )

    library = {
        "dual_stt": {"first": [fast, steady]},
        "speak": ["tts", {"stage": "transport", "ms": [30, 50]}],
        "think": {
            "all": [["llm"], {"first": [{"stage": "llm", "ms": [180, 500]}, {"stage": "llm", "ms": [200, 350]}]}]
        },
    }
    assert latency(["vad", {"use": "dual_stt"}, {"use": "think"}, {"use": "speak"}], library) == (
        430,
        910,
    ), "sub-pipelines nest"
    assert latency({"all": [{"use": "speak"}, ["vad", {"use": "speak"}]]}, library) == (150, 310), (
        "a sub-pipeline may be used twice"
    )
    assert latency([], library) == (0, 0)

    for bad in (
        {"first": []},
        {"stage": "stt", "ms": [300, 200]},
        {"stage": "stt", "ms": [-20, 200]},
        {"stage": "asr", "ms": [80, 120]},
        "asr",
        {"use": "missing"},
        {"stage": "stt", "first": ["vad"]},
    ):
        with pytest.raises(ValueError):
            latency(bad, library)
    with pytest.raises(ValueError):
        latency({"use": "a"}, {"a": ["vad", {"use": "b"}], "b": {"first": [{"use": "a"}]}})

    assert [grade(ms) for ms in (450, 600, 601, 1200, 1201, 1500, 1501)] == [
        "premium",
        "premium",
        "common",
        "common",
        "slow",
        "slow",
        "broken",
    ], "premium up to 600 ms, common up to 1200, broken past 1500"
