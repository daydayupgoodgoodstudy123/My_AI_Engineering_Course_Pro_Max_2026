import asyncio
import math
import time

import pytest
from rtloop.capture import Capture
from rtloop.dialog import Dialog
from rtloop.graph import critical_path, schedule
from rtloop.meter import FLOOR_DBFS
from rtloop.pipeline import Stats, run_pipeline
from rtloop.ring import RingBuffer
from rtloop.traces import STAGES, TraceStore

MS = 1_000_000  # nanoseconds


def tone(freq: float, sr: int, seconds: float, amp: float = 1.0) -> list[float]:
    return [amp * math.sin(2.0 * math.pi * freq * i / sr) for i in range(int(sr * seconds))]


def callbacks(signal: list[float], size: int) -> list[list[float]]:
    """The chunks an audio callback delivers, size samples at a time."""
    return [signal[i : i + size] for i in range(0, len(signal), size)]


@pytest.mark.skip("Part 1")
def test_capture_path() -> None:
    """Mic audio reaches the loop as whole 20 ms frames at the right level, even after a stall."""
    sr = 16000
    mic = tone(1000, sr, 1.0) + [0.0] * 8000  # one second of a full-scale tone, then a muted mic
    capture = Capture(sr, frame_ms=20, buffer_ms=100)
    frames = []
    for chunk in callbacks(mic, 256):
        capture.write(chunk)
        frames += capture.frames()
    assert [f.t_ns for f in frames] == [i * 20 * MS for i in range(75)], "one frame per 20 ms of audio"
    assert all(f.samples == mic[i * 320 : (i + 1) * 320] for i, f in enumerate(frames)), (
        "each frame is the next 20 ms of the mic stream"
    )
    assert all(f.dbfs == pytest.approx(-3.0103, abs=1e-3) for f in frames[:50]), (
        "a full-scale sine reads -3.01 dBFS"
    )
    assert all(f.dbfs == FLOOR_DBFS for f in frames[50:]), "a muted mic reads the floor"

    laptop = Capture(44100)  # the built-in mic of many laptops runs at 44.1 kHz
    laptop.write(tone(441, 44100, 0.1))
    assert [(f.t_ns, len(f.samples)) for f in laptop.frames()] == [(i * 20 * MS, 882) for i in range(5)], (
        "a frame is 20 ms at any sample rate"
    )

    ring = RingBuffer(5)
    ring.write([1, 2, 3])
    ring.write([4, 5, 6, 7])
    assert ring.read(10) == [3, 4, 5, 6, 7], "a full ring overwrites its oldest samples"
    assert (ring.level(), ring.dropped) == (0, 2), "every overwritten sample is counted"

    stalled = Capture(sr, buffer_ms=200)
    for chunk in callbacks(tone(1000, sr, 0.5), 320):  # the loop is stuck for half a second
        stalled.write(chunk)
    assert [f.t_ns for f in stalled.frames()] == [(300 + 20 * i) * MS for i in range(10)], (
        "after a stall the loop gets the newest audio, at its own capture time"
    )

    ring = RingBuffer(sr)  # one second
    chunk = [0.5] * 320
    start = time.perf_counter()
    for _ in range(100):  # the loop is stuck for 2 seconds; the callback keeps writing
        ring.write(chunk)
    assert time.perf_counter() - start < 0.1, "the audio callback should stay fast when the loop stalls"
    assert ring.dropped == 100 * 320 - sr


WALL = 1_793_491_200_123_456_789  # time.time_ns() on 2026-11-01, far past 2**53


def turn_marks(start: int, *gaps: int) -> dict[str, int]:
    """Marks for the first stages of a turn: start, then each gap after the stage before."""
    marks, t = {}, start
    for stage, gap in zip(STAGES, (0, *gaps)):
        t += gap
        marks[stage] = t
    return marks


@pytest.mark.skip("Part 2")
def test_trace_store(tmp_path) -> None:
    """Latency marks round-trip in integer nanoseconds, and slow turns are found exactly."""
    path = str(tmp_path / "traces.sqlite3")
    on_budget = turn_marks(WALL, 150 * MS, 100 * MS, 250 * MS)  # first audio 500 ms after speech_end
    cached = turn_marks(WALL + 7_000_000_001, 120 * MS, 0, 380 * MS + 1)  # instant first token
    cut_off = turn_marks(WALL + 9_000_000_003, 140 * MS)  # the user cut in before the reply
    slow = turn_marks(WALL + 12_345_678_901, 300 * MS, 250 * MS, 150 * MS)

    store = TraceStore(path)
    assert store.record("call-1", on_budget) == 1
    assert store.record("call-2", cached) == 1, "turns are numbered within their session"
    assert store.record("call-1", cut_off) == 2
    assert store.record("call-1", slow) == 3
    for bad in (
        {"speech_end": 10, "transcript": 9},  # the clock went backwards
        {"speech_end": 10, "first_audio": 20},  # two stages are missing in between
        {"transcript": 10},  # no end of speech
        {"speech_end": WALL / 1e9},  # seconds, as a float
        {"speech_end": 10, "tts_start": 20},  # not a stage
    ):
        with pytest.raises(ValueError):
            store.record("call-1", bad)
    store.close()

    reopened = TraceStore(path)
    assert [reopened.turn("call-1", 1), reopened.turn("call-2", 1)] == [on_budget, cached], (
        "marks round-trip exactly, in integer nanoseconds"
    )
    assert reopened.turn("call-1", 2) == cut_off, "a turn cut off early keeps the marks it has"
    with pytest.raises(KeyError):
        reopened.turn("call-1", 4)
    assert reopened.slow_turns(500 * MS) == [("call-2", 1), ("call-1", 3)], (
        "slow means over budget, in the order the turns were recorded"
    )
    assert reopened.record("call-1", turn_marks(WALL + 20_000_000_000)) == 4, (
        "numbering carries on after a reopen"
    )
    reopened.close()


@pytest.mark.skip("Part 3")
def test_barge_in() -> None:
    """The user can cut the assistant off: playback stops at once and the rest is dropped."""
    dialog = Dialog(barge_in_frames=3)
    first = dialog.user_turn(0, "book a table for two")
    assert (first, dialog.state) == (1, "thinking")
    dialog.audio(300 * MS, first, "Sure,", 320 * MS)
    assert dialog.state == "speaking", "the first chunk to play gives the assistant the floor"
    dialog.audio(400 * MS, first, "what time", 320 * MS)
    dialog.audio(500 * MS, first, "works for you?", 320 * MS)
    for t in range(640, 760, 20):  # leftover echo of the assistant: speech in every other frame
        dialog.mic(t * MS, t % 40 == 0)
    assert dialog.state == "speaking", (
        "isolated speech frames (echo, a cough) do not cut the assistant off"
    )
    assert dialog.played == [(300 * MS, 620 * MS, "Sure,"), (620 * MS, 940 * MS, "what time")], (
        "chunks play back to back, in order"
    )
    for t in (760, 780, 800):
        dialog.mic(t * MS, True)
    assert dialog.state == "listening", "three speech frames in a row hand the floor to the user"
    assert dialog.played[-1] == (620 * MS, 800 * MS, "what time"), (
        "a barge-in stops playback at once, even in the middle of a chunk"
    )

    second = dialog.user_turn(1500 * MS, "make it three people")
    dialog.audio(1550 * MS, first, "works for you? Seven?", 320 * MS)  # still in flight from reply 1
    dialog.reply_done(1560 * MS, first)
    dialog.audio(1600 * MS, second, "Three it is.", 320 * MS)
    dialog.reply_done(1650 * MS, second)
    dialog.mic(1900 * MS, False)
    assert dialog.state == "speaking", "a reply holds the floor until its last chunk has played"
    dialog.mic(1920 * MS, False)
    assert dialog.played[2:] == [(1600 * MS, 1920 * MS, "Three it is.")], (
        "chunks of a cancelled reply never play"
    )
    assert dialog.state == "listening", "the floor comes back the moment the last chunk ends"

    third = dialog.user_turn(3000 * MS, "and what's the weather")
    for t in (3100, 3120, 3140):  # the user keeps talking before the reply has started
        dialog.mic(t * MS, True)
    dialog.audio(3200 * MS, third, "It's sunny.", 320 * MS)
    assert dialog.state == "listening" and len(dialog.played) == 3, (
        "talking over a reply that has not started yet cancels it too"
    )
    fourth = dialog.user_turn(4000 * MS, "is it warm?")
    dialog.audio(4100 * MS, fourth, "Yes, about twenty degrees.", 320 * MS)
    dialog.user_turn(4200 * MS, "thanks")  # typed in the app while the reply plays
    assert dialog.played[3:] == [(4100 * MS, 4200 * MS, "Yes, about twenty degrees.")], (
        "a new user turn cuts the reply off the same way"
    )
    assert dialog.history == [
        ("user", "book a table for two"),
        ("assistant", "Sure, what time"),
        ("user", "make it three people"),
        ("assistant", "Three it is."),
        ("user", "and what's the weather"),
        ("user", "is it warm?"),
        ("assistant", "Yes, about twenty degrees."),
        ("user", "thanks"),
    ], "the history keeps what the user heard, and nothing for a reply that never made a sound"

    capture, live = Capture(16000), Dialog()
    news = live.user_turn(0, "read me the news")
    live.audio(0, news, "Here are today's headlines.", 2000 * MS)
    capture.write([0.0] * 8000 + tone(220, 16000, 0.5, amp=0.1))  # 0.5 s of silence, then the user
    for frame in capture.frames():
        live.mic(frame.t_ns, frame.dbfs > -40.0)
    assert live.played == [(0, 540 * MS, "Here are today's headlines.")], "barge-in from real mic audio"


async def mic_stream(n: int):
    """A real-time mic: one frame per turn of the event loop, ready or not."""
    for i in range(n):
        yield i
        await asyncio.sleep(0)


@pytest.mark.skip("Part 4")
def test_stage_pipeline() -> None:
    """Stages run on bounded queues: the mic never waits, and a hang-up stops everything."""
    got: list[int] = []

    async def double(x):
        return 2 * x

    async def collect(x):
        got.append(x)

    stats = asyncio.run(asyncio.wait_for(run_pipeline(mic_stream(20), [double, double], collect), 2.0))
    assert got == [4 * i for i in range(20)] and stats == Stats(delivered=20), (
        "every frame passes through every stage, in order"
    )

    tagged: list[int] = []
    heard: list[int] = []
    lag: list[int] = []

    async def tag(x):
        tagged.append(x)
        return x

    async def slow_stt(x):  # five turns of the loop per frame: slower than the mic
        lag.append(len(tagged) - len(heard))
        heard.append(x)
        for _ in range(5):
            await asyncio.sleep(0)

    stats = asyncio.run(asyncio.wait_for(run_pipeline(mic_stream(200), [tag], slow_stt, maxsize=4), 2.0))
    assert heard == sorted(heard) and heard[-1] == 199, "the newest frame always gets through, in order"
    # tagged but not heard yet: at most a full queue, the frame tag holds, the frame in slow_stt
    assert max(lag) <= 4 + 2, "a full queue makes the stage in front of it wait"
    assert stats.dropped > 0 and stats.delivered + stats.dropped == 200, (
        "a slow consumer makes the mic drop its oldest frames instead of waiting"
    )

    async def flaky(x):
        if x == 3:
            raise ValueError("cannot decode frame 3")
        return x

    async def playback(x):
        if x == 5:
            raise OSError("audio device underrun")
        got.append(x)

    got.clear()
    stats = asyncio.run(asyncio.wait_for(run_pipeline(mic_stream(8), [flaky], playback), 2.0))
    assert got == [0, 1, 2, 4, 6, 7] and stats == Stats(delivered=6, errors=2), (
        "a stage or the sink that fails on one frame loses only that frame"
    )

    events: list[str] = []

    async def tts(x):
        if x == 0:
            try:
                await asyncio.Event().wait()  # the first request never answers
            finally:
                await asyncio.sleep(0.01)  # closing the TTS connection takes a round trip
                events.append("tts closed")
        return x

    async def speaker(x):
        events.append(f"play {x}")

    async def hang_up():
        call = asyncio.create_task(run_pipeline(mic_stream(10), [tts], speaker))
        for _ in range(20):
            await asyncio.sleep(0)
        call.cancel()
        done, _ = await asyncio.wait({call}, timeout=1.0)
        others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        return bool(done), call.cancelled() if done else False, len(others)

    stopped, cancelled, leftover = asyncio.run(hang_up())
    assert stopped, "hanging up stops the pipeline"
    assert cancelled, "the cancellation propagates out of run_pipeline"
    assert leftover == 0, "no stage task outlives run_pipeline"
    assert events == ["tts closed"], (
        "the request in flight finishes its cleanup, and nothing plays after"
    )


VOICE = {  # keys sorted, the way the config file stores them
    "aec": {"ms": 10, "inputs": ["mic"], "reference": ["speaker"]},
    "captions": {"ms": 30, "inputs": ["stt"]},
    "llm": {"ms": 100, "inputs": ["turn", "stt"]},
    "mic": {"ms": 20, "inputs": []},
    "speaker": {"ms": 20, "inputs": ["tts"]},
    "stt": {"ms": 150, "inputs": ["vad"]},
    "tts": {"ms": 100, "inputs": ["llm"]},
    "turn": {"ms": 5, "inputs": ["vad", "stt"]},
    "vad": {"ms": 10, "inputs": ["aec"]},
}


@pytest.mark.skip("Part 5")
def test_processing_graph() -> None:
    """Order the processing graph, refuse real loops, and find the chain that sets the latency."""
    order = schedule(VOICE)
    assert sorted(order) == sorted(VOICE), "every stage is scheduled once"
    assert all(order.index(i) < order.index(s) for s in VOICE for i in VOICE[s]["inputs"]), (
        "a stage runs after all of its inputs"
    )
    assert critical_path(VOICE, "speaker") == (
        415,
        ["mic", "aec", "vad", "stt", "turn", "llm", "tts", "speaker"],
    ), "the slowest chain of inputs sets the latency"
    assert critical_path(VOICE, "captions") == (220, ["mic", "aec", "vad", "stt", "captions"])
    mixer = {
        "left": {"ms": 5, "inputs": []},
        "right": {"ms": 5, "inputs": []},
        "mix": {"ms": 2, "inputs": ["right", "left"]},
    }
    assert critical_path(mixer, "mix") == (7, ["right", "mix"]), "a tie goes to the input listed first"

    looped = {**VOICE, "stt": {"ms": 150, "inputs": ["vad", "speaker"]}}  # no AEC: STT hears the reply
    with pytest.raises(ValueError) as loop:
        schedule(looped)
    message = str(loop.value)
    assert all(s in message for s in ("stt", "speaker", "tts", "llm")) and "captions" not in message, (
        "the error names the stages in the loop, not everything behind it"
    )
    with pytest.raises(ValueError):
        schedule({"echo": {"ms": 1, "inputs": ["echo"]}})
    with pytest.raises(ValueError):
        schedule({**VOICE, "vad": {"ms": 10, "inputs": ["aecc"]}})
    with pytest.raises(ValueError):
        schedule({**VOICE, "aec": {"ms": 10, "inputs": ["mic"], "reference": ["speakers"]}})

    rack = {"mic": {"ms": 1, "inputs": []}}
    previous = ["mic"]
    for i in range(1, 21):  # a stereo chain: each stage reads both channels of the stage before
        rack[f"left{i}"] = {"ms": 1, "inputs": previous}
        rack[f"right{i}"] = {"ms": 1, "inputs": previous}
        previous = [f"left{i}", f"right{i}"]
    rack["speaker"] = {"ms": 1, "inputs": previous}
    start = time.perf_counter()
    total, chain = critical_path(rack, "speaker")
    assert time.perf_counter() - start < 0.05, "critical_path should be fast on a deep graph"
    assert (total, len(chain)) == (22, 22)
