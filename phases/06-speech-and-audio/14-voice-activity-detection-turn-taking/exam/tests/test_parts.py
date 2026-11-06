import asyncio
import json
import random
import time

import pytest
from turnkit.cascade import cascade
from turnkit.energy import FLOOR_DBFS, apply_hangover, energy_gate, frame_levels
from turnkit.overlap import overlap_tree
from turnkit.segments import Segment, SegmentTable
from turnkit.service import TurnService
from turnkit.turns import TurnDetector


def steady(level_dbfs: float, frames: int) -> list[float]:
    """160-sample frames (20 ms at 8 kHz) whose RMS level is exactly level_dbfs."""
    a = 10 ** (level_dbfs / 20)
    return [a, -a] * (80 * frames)


def synth_chunk(kind: str, rng: random.Random, n: int = 320) -> list[float]:
    """One 20 ms chunk at 16 kHz, the same recipe as the lesson's synthetic stream."""
    if kind == "speech":
        return [0.2 * rng.gauss(0, 1.0) for _ in range(n)]
    if kind == "cough":
        return [0.8 * rng.gauss(0, 1.0) if i < n // 5 else 0.001 * rng.gauss(0, 1.0) for i in range(n)]
    return [0.002 * rng.gauss(0, 1.0) for _ in range(n)]


class RecordingSTT:
    """Stands in for a streaming STT that supports flush."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def send_audio(self, samples: list[float]) -> None:
        self.calls.append(("audio", samples))

    def send_flush(self) -> None:
        self.calls.append(("flush",))


def run(detector: TurnDetector, pattern: str) -> list[tuple[str, int, int]]:
    """Feed one frame per character ('#' is speech) and collect (kind, sample, decided)."""
    events = [detector.update(c == "#") for c in pattern]
    return [(e.kind, e.sample, e.decided) for e in events if e is not None]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def chunked(signal: list[float], sizes: list[int]):
    pos = 0
    for size in sizes:
        yield signal[pos : pos + size]
        pos += size


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Server-sent events: an 'event:' line and a 'data:' line, then a blank line."""
    assert text.endswith("\n\n"), "every event ends with a blank line"
    events = []
    for block in text[:-2].split("\n\n"):
        lines = block.split("\n")
        assert len(lines) == 2 and lines[0].startswith("event: ") and lines[1].startswith("data: "), (
            f"one event line and one data line per event, got {block!r}"
        )
        events.append((lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])))
    return events


@pytest.mark.skip("Part 1")
def test_energy_gate() -> None:
    """The gate measures levels in dBFS, applies the hangover and keeps up with a long stream."""
    assert frame_levels([0.5, -0.5] * 80 + [0.3, -0.4] * 80 + [0.0] * 160, 160) == pytest.approx(
        [-6.0206, -9.0309, FLOOR_DBFS], abs=1e-4
    ), "a frame's level is 20 * log10(RMS), with full scale at 0 dBFS"

    sr = 8000
    signal = (
        steady(-54, 5) + steady(-30, 10) + steady(-54, 2) + steady(-12, 10)
        + steady(-54, 8) + steady(-38, 1) + steady(-42, 1) + steady(-54, 3)
    )
    loud = [False] * 5 + [True] * 10 + [False] * 2 + [True] * 10 + [False] * 8 + [True, False] + [False] * 3
    assert energy_gate(signal, sr, hangover_ms=0) == loud, (
        "a frame is speech when its RMS level is above threshold_dbfs"
    )

    dip = steady(-54, 5) + steady(-30, 10) + steady(-54, 2) + steady(-30, 10) + steady(-54, 10)
    flags = energy_gate(dip, sr)
    assert flags[:5] == [False] * 5, "frames before the first loud frame are not speech"
    assert flags == [False] * 5 + [True] * 27 + [False] * 5, (
        "a loud frame and the hangover_ms after it are speech, so short dips stay speech"
    )
    assert apply_hangover([True, False, False, False], 2) == [True, True, True, False], (
        "a loud first frame bridges like any other"
    )

    rng = random.Random(0)
    # the user talks for 20 s, then listens to a long answer
    five_minutes = [rng.random() < 0.3 for _ in range(1000)] + [False] * 15000
    start = time.perf_counter()
    apply_hangover(five_minutes, 5)
    assert time.perf_counter() - start < 0.1, "the hangover pass should keep up with a long stream"


@pytest.mark.skip("Part 2")
def test_segment_table(tmp_path) -> None:
    """Segments are kept to the sample, merge when they touch, and survive a reopen."""
    path = str(tmp_path / "segments.sqlite3")
    table = SegmentTable(path)
    assert table.add("call-7", 16000, 16001, 24005) == Segment("call-7", 16000, 16001, 24005), (
        "segments are kept to the sample"
    )
    table.add("call-7", 16000, 40000, 48000)
    table.add("call-7", 16000, 1001, 8001)
    assert table.add("call-7", 16000, 24005, 40000) == Segment("call-7", 16000, 16001, 48000), (
        "a segment that touches its neighbours merges with both"
    )
    assert table.add("call-7", 16000, 0, 1000) == Segment("call-7", 16000, 0, 1000), (
        "a one-sample gap keeps segments apart"
    )
    assert table.add("call-7", 16000, 30000, 31000) == Segment("call-7", 16000, 16001, 48000), (
        "a segment inside a stored one merges into it"
    )
    late = 13 * 3600 * 48000 + 1  # 13 hours into a 48 kHz room recording
    table.add("room-2", 48000, late, late + 959)
    table.close()

    reopened = SegmentTable(path)
    assert reopened.segments("call-7") == [
        Segment("call-7", 16000, 0, 1000),
        Segment("call-7", 16000, 1001, 8001),
        Segment("call-7", 16000, 16001, 48000),
    ], "a reopened table has the same segments, to the sample, in time order"
    assert reopened.add("room-2", 48000, 0, late) == Segment("room-2", 48000, 0, late + 959), (
        "stored segments still merge after a reopen"
    )
    assert reopened.segments("room-2") == [Segment("room-2", 48000, 0, late + 959)]
    assert len(reopened.segments("call-7")) == 3, "segments merge only within their own recording"
    assert reopened.segments("nobody") == []
    with pytest.raises(ValueError):
        reopened.add("call-7", 8000, 0, 100)
    with pytest.raises(ValueError):
        reopened.add("call-7", 16000, 500, 500)
    with pytest.raises(ValueError):
        reopened.add("call-7", 16000, -160, 0)
    reopened.close()


@pytest.mark.skip("Part 3")
def test_turn_detector() -> None:
    """Turns start after enough speech, end after enough silence, and carry their pre-roll."""

    # 8 kHz with 160-sample frames: 100 ms is 5 frames, 200 ms is 10, 60 ms is 3
    def detector(pre_roll_ms: int = 60) -> TurnDetector:
        return TurnDetector(8000, 160, min_speech_ms=100, silence_hangover_ms=200, pre_roll_ms=pre_roll_ms)

    events = run(detector(), "." * 10 + "#" * 20 + "." * 4 + "#" * 6 + "." * 12)
    assert events[:1] == [("start", 1120, 2400)], (
        "a turn starts min_speech_ms into the speech, with pre_roll_ms of audio before the onset"
    )
    assert events[1:] == [("end", 6400, 8000)], (
        "a short pause does not end the turn; it ends where its last speech frame ends, a hangover later"
    )
    assert run(detector(), ("#" + "." * 9) * 20) == [], "isolated clicks never add up to a turn"
    assert run(detector(), "#" * 4 + "." * 20) == [], "speech shorter than min_speech_ms is not a turn"
    assert run(detector(pre_roll_ms=300), "#" * 6 + "." * 11 + "#" * 6) == [
        ("start", 0, 800),
        ("end", 960, 2560),
        ("start", 960, 3520),
    ], "pre-roll never reaches before the stream or into the previous turn"
    assert run(TurnDetector(16000, 320), "#" * 13) == [("start", 0, 4160)], (
        "a turn needs min_speech_ms of speech, even when that is not a whole number of frames"
    )

    live = detector()
    assert run(live, "." * 3 + "#" * 8 + "." * 3) == [("start", 0, 1280)]
    end = live.flush()
    assert end is not None and (end.kind, end.sample, end.decided) == ("end", 1760, 2240), (
        "flush ends the turn at its last speech frame, without waiting for the hangover"
    )
    assert run(live, "#" * 3) == [] and live.flush() is None, "flush drops speech too short to be a turn"
    assert run(live, "#" * 2) == [] and live.flush() is None, (
        "after a flush, a turn needs min_speech_ms of new speech"
    )
    assert run(live, "#" * 5) == [("start", 2560, 3840)], "speech after a flush can start a new turn"
    end = live.flush()
    assert end is not None and (end.kind, end.sample, end.decided) == ("end", 3840, 3840), (
        "flush right after a speech frame ends the turn at the end of that frame"
    )
    assert run(live, "#" * 5) == [("start", 3840, 4640)], "pre-roll never reaches into a flushed turn"

    rng = random.Random(42)
    lesson = [
        ("silence", 10), ("speech", 40), ("silence", 30), ("cough", 1),
        ("silence", 10), ("speech", 25), ("silence", 35),
    ]
    signal = [x for kind, count in lesson for _ in range(count) for x in synth_chunk(kind, rng)]
    stt = RecordingSTT()
    turns = TurnService(SegmentTable(), 16000, stt=stt).listen("demo", signal)
    assert turns == [Segment("demo", 16000, 0, 17600), Segment("demo", 16000, 24320, 38720)], (
        "the lesson's stream holds two turns, and the cough is not one"
    )
    assert stt.calls == [
        ("audio", signal[0:17600]),
        ("flush",),
        ("audio", signal[24320:38720]),
        ("flush",),
    ], "each finished turn goes to the STT once, followed by a flush"


PATTERN = "..s.ss.nsss..n.sn.."  # '.' quiet, 'n' noise the gate passes, 's' speech
LEVEL = {".": 0.0, "n": 0.3, "s": 0.8}


@pytest.mark.skip("Part 4")
def test_cascade_stream() -> None:
    """The model runs only behind the gate, with its context, and changes stream out as SSE."""
    sr = 1000  # 20 ms frames of 20 samples
    signal = [LEVEL[c] for c in PATTERN for _ in range(20)] + [0.8] * 7
    seen: list[list[float]] = []

    def gate(frame: list[float]) -> bool:
        return max(abs(x) for x in frame) > 0.1

    def model(context: list[float]) -> float:
        seen.append(context)
        return sum(x > 0.5 for x in context) / len(context)

    gated = [i for i, c in enumerate(PATTERN) if c != "."]
    contexts = [signal[max(0, i - 2) * 20 : (i + 1) * 20] for i in gated]
    for sizes in ([len(signal)], [1] * len(signal), [7, 0, 30, 2, 50, 21, 300]):
        seen.clear()
        events = parse_sse("".join(collect(cascade(chunked(signal, sizes), sr, gate, model))))
        assert seen == contexts, (
            "the model runs once per frame the gate passes, on it and the frames before it, "
            f"chunks {sizes[:6]}"
        )
        assert events[:-1] == [
            ("speech", {"sample": 80}),
            ("silence", {"sample": 120}),
            ("speech", {"sample": 180}),
            ("silence", {"sample": 220}),
        ], f"speech starts and stops where the cascade decides, e.g. with chunks {sizes[:6]}"
        assert events[-1] == ("stats", {"frames": 19, "model_calls": 10, "skipped": 9}), (
            "the stream ends with frame and model-call counts"
        )

    pulled: list[int] = []

    async def probe():
        for i in range(200):
            pulled.append(i)
            yield [0.0] * 20 if i < 3 else [0.8] * 20

    async def first_event() -> str:
        agen = cascade(probe(), sr, gate, model)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert parse_sse(asyncio.run(first_event())) == [("speech", {"sample": 80})]
    assert len(pulled) <= 5, "send each change as soon as its frame is complete"


def spurts_ms(*rows: tuple[str, int, int]) -> list[tuple[str, int, int]]:
    """(speaker, start ms, end ms) as sample ranges at 16 kHz."""
    return [(who, a * 16, b * 16) for who, a, b in rows]


def node(who: str, a: int, b: int, kind: str, *inside: dict) -> dict:
    return {"speaker": who, "start": a * 16, "end": b * 16, "kind": kind, "inside": list(inside)}


@pytest.mark.skip("Part 5")
def test_overlap_tree() -> None:
    """Talk spurts nest inside the spurt that holds the floor, at any depth."""
    assert overlap_tree(spurts_ms(("A", 0, 3000), ("B", 1000, 1999), ("C", 2000, 3000)), 16000) == [
        node("A", 0, 3000, "turn", node("B", 1000, 1999, "backchannel"), node("C", 2000, 3000, "overlap")),
    ], "a nested spurt is a backchannel when shorter than backchannel_ms, else an overlap"
    nested = spurts_ms(("B", 1200, 1500), ("A", 0, 5000), ("C", 2000, 4000), ("B", 2500, 2800))
    assert overlap_tree(nested, 16000) == [
        node(
            "A", 0, 5000, "turn",
            node("B", 1200, 1500, "backchannel"),
            node("C", 2000, 4000, "overlap", node("B", 2500, 2800, "backchannel")),
        ),
    ], "a spurt goes inside the innermost spurt that contains it"
    assert overlap_tree(spurts_ms(("A", 0, 5000), ("B", 4800, 7000)), 16000) == [
        node("A", 0, 5000, "turn"),
        node("B", 4800, 7000, "turn"),
    ], "a spurt that outlasts the current speaker is a new turn"
    touching = spurts_ms(("B", 4800, 7000), ("C", 7000, 8000), ("A", 7000, 9500), ("A", 9500, 9900))
    assert overlap_tree(touching, 16000) == [
        node("B", 4800, 7000, "turn"),
        node("A", 7000, 9500, "turn", node("C", 7000, 8000, "overlap")),
        node("A", 9500, 9900, "turn"),
    ], "spurts that only touch do not nest; of two that start together, the longer one holds the floor"

    conversation = spurts_ms(
        ("A", 0, 5000), ("B", 1200, 1500), ("C", 2000, 4000), ("B", 2500, 2800),
        ("B", 4800, 7000), ("C", 7000, 8000), ("A", 7000, 9500), ("A", 9500, 9900),
    )
    random.Random(7).shuffle(conversation)
    assert overlap_tree(conversation, 16000) == [
        node(
            "A", 0, 5000, "turn",
            node("B", 1200, 1500, "backchannel"),
            node("C", 2000, 4000, "overlap", node("B", 2500, 2800, "backchannel")),
        ),
        node("B", 4800, 7000, "turn"),
        node("A", 7000, 9500, "turn", node("C", 7000, 8000, "overlap")),
        node("A", 9500, 9900, "turn"),
    ], "the whole conversation, given in any order"
    with pytest.raises(ValueError):
        overlap_tree(spurts_ms(("A", 0, 5000), ("B", 1000, 2000), ("A", 4000, 6000)), 16000)
    with pytest.raises(ValueError):
        overlap_tree(spurts_ms(("A", 0, 5000), ("B", 2000, 2000)), 16000)
