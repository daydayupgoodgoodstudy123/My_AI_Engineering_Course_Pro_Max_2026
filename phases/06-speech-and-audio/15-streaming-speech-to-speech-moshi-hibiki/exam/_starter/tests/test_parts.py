import asyncio
import json
import math
import time

import pytest
from duplex.delay import MOSHI_DELAYS, delay, ready_ms, undelay
from duplex.log import Frame, SessionLog
from duplex.mimi import SAMPLE_RATE, encode
from duplex.model import DuplexSession, DuplexStepper, ToyMoshi
from duplex.monitor import timeline
from duplex.monologue import Word, align
from duplex.service import DuplexService
from duplex.tokens import AUDIO_START, CODEBOOKS, EPAD, PAD, TEXT_START, UNSET


def tone(freq: float, seconds: float) -> list[float]:
    """A plain sine at Mimi's 24 kHz."""
    n = round(seconds * SAMPLE_RATE)
    return [0.5 * math.sin(2.0 * math.pi * freq * i / SAMPLE_RATE) for i in range(n)]


def collect(agen, limit: int = 1000) -> list:
    async def drain() -> list:
        items = []
        async for item in agen:
            items.append(item)
            if len(items) >= limit:
                break
        return items

    return asyncio.run(drain())


async def bursts(packets: list[dict], sizes: list[int]):
    pos = 0
    for size in sizes:
        await asyncio.sleep(0)
        yield packets[pos : pos + size]
        pos += size


class Probe:
    """Stands in for the model and records what the stepper shows each head."""

    def __init__(self) -> None:
        self.heard: list[int] = []
        self.said: list = []
        self.newest: list[tuple[list[int], list[int]]] = []
        self.depth: list[tuple[int, list[int]]] = []

    def initial(self) -> tuple:
        return (0, None, None, None)

    def advance(self, state: tuple, user: list[int], text: int, audio: list[int]) -> tuple:
        return (state[0] + 1, text, list(user), list(audio))

    def next_text(self, state: tuple) -> int:
        self.heard.append(state[0])
        self.said.append(state[1])
        self.newest.append((state[2], state[3]))
        return 100 + state[0]

    def next_code(self, state: tuple, text: int, prefix: list[int]) -> int:
        self.depth.append((text, list(prefix)))
        return 7 * len(prefix)


@pytest.mark.skip("Part 1")
def test_duplex_step() -> None:
    """Each 80 ms step hears one user frame, then predicts a text token, then codebooks 0-7."""
    pcm = tone(220.0, 0.33)  # four 80 ms frames and part of a fifth
    assert [len(codes) for codes in encode(pcm)] == [4] * CODEBOOKS, (
        "encode keeps Mimi's codebook-major layout: 8 codebooks of 4 frames"
    )
    replies = DuplexSession(ToyMoshi()).hear(pcm)
    assert [reply.frame for reply in replies] == [0, 1, 2, 3], "one reply per user frame"

    probe = Probe()
    stepper = DuplexStepper(probe)
    mic = [[10 * t + k for k in range(CODEBOOKS)] for t in range(100)]
    for frame in mic:
        stepper.step(frame)
    assert probe.heard[:3] == [1, 2, 3], "frame t is predicted after hearing user frames 0..t"
    assert probe.said[:3] == [TEXT_START, 101, 102], "the context holds the model's own text up to t - 1"
    assert probe.newest[:2] == [
        (mic[0], [AUDIO_START] * CODEBOOKS),
        (mic[1], [0, 7, 14, 21, 28, 35, 42, 49]),
    ], "step t folds in user frame t and the model's own audio from t - 1"
    assert probe.depth[:CODEBOOKS] == [(101, [7 * i for i in range(k)]) for k in range(CODEBOOKS)], (
        "codebook k is predicted after the text token and codebooks 0..k-1, semantic first"
    )

    user = [[(31 * t + 7 * k) % 1024 for k in range(CODEBOOKS)] for t in range(1500)]
    long_session = DuplexStepper(ToyMoshi())
    start = time.perf_counter()
    for frame in user:
        long_session.step(frame)
    assert time.perf_counter() - start < 0.1, "a step costs the same two minutes into a session"
    assert probe.heard == list(range(1, 101)), "100 frames in, the context still holds frame 0"


@pytest.mark.skip("Part 2")
def test_session_log(tmp_path) -> None:
    """Both sides of every frame survive the log exactly, including a reopen."""
    path = str(tmp_path / "sessions.sqlite3")
    edge = [0, 1023, 512, 1, 0, 7, 1023, 64]
    other = [1023, 0, 0, 0, 0, 0, 0, 1]

    log = SessionLog(path)
    log.add_model("call-1", 1, 4021, other)  # the generation loop got to frame 1 first
    assert log.frames("call-1") == [], "a frame shows up once both of its sides are logged"
    log.add_user("call-1", 1, edge)
    log.add_user("call-1", 0, other)
    log.add_model("call-1", 0, PAD, edge)
    log.add_user("call-1", 2, edge)  # the model's frame 2 is still being generated
    log.add_user("call-2", 0, edge)
    log.add_model("call-2", 0, EPAD, other)
    expected = [Frame(0, other, edge, PAD), Frame(1, edge, other, 4021)]
    assert log.frames("call-1") == expected, "complete frames come back exactly, in frame order"
    with pytest.raises(KeyError):
        log.frame("call-1", 2)
    log.close()

    reopened = SessionLog(path)
    assert reopened.frames("call-1") == expected, "a reopened log keeps every frame"
    assert reopened.frame("call-2", 0) == Frame(0, edge, other, EPAD), "sessions are kept apart"
    reopened.add_model("call-1", 2, 77, other)
    assert reopened.frame("call-1", 2) == Frame(2, edge, other, 77), "the second side completes a frame"
    with pytest.raises(ValueError):
        reopened.add_user("call-1", 3, edge[:7])
    with pytest.raises(ValueError):
        reopened.add_model("call-1", 3, 5, edge[:7] + [1024])
    with pytest.raises(ValueError):
        reopened.add_user("call-1", 0, edge)
    with pytest.raises(ValueError):
        reopened.add_model("call-1", 1, 4021, other)
    reopened.close()


@pytest.mark.skip("Part 3")
def test_inner_monologue() -> None:
    """The model's timed words are laid onto its text stream, each announced by an EPAD."""
    P, E = PAD, EPAD
    assert align([Word([11], 0.24), Word([12, 13], 0.62)], 10) == [P, P, E, 11, P, P, E, 12, 13, P], (
        "a word starts in the frame that holds its start time, announced in the frame before"
    )
    stream = align([Word([14], 2.32), Word([15], 16.08)], 210)
    assert {t: token for t, token in enumerate(stream) if token != P} == {28: E, 29: 14, 200: E, 201: 15}, (
        "2.32 s falls in frame 29 and 16.08 s in frame 201"
    )
    assert align([Word([21], 0.0)], 3) == [E, 21, P], (
        "a word at 0 s is announced in frame 0 and starts in frame 1"
    )
    assert align([Word([31, 32, 33], 0.0), Word([34], 0.1)], 7) == [E, 31, 32, 33, E, 34, P], (
        "fast speech pushes a word later; words never overwrite each other"
    )
    assert align([Word([41, 42], 0.0)], 3) == [E, 41, 42], "a word can end in the last frame"
    with pytest.raises(ValueError):
        align([Word([41, 42], 0.0)], 2)
    with pytest.raises(ValueError):
        align([Word([51], 0.5), Word([52], 0.2)], 20)

    service = DuplexService(SessionLog())
    words = [Word([11], 0.0), Word([12, 13], 0.08), Word([14], 1.27)]
    assert service.record("demo", tone(220.0, 1.6), tone(330.0, 1.6), words) == 20
    assert service.transcript("demo") == [(1, [11]), (3, [12, 13]), (15, [14])], (
        "the logged inner monologue gives the transcript back for free"
    )


def packets(pattern: str) -> list[dict]:
    """'v' voiced, '.' silent, ' ' lost."""
    return [{"frame": t, "voiced": c == "v"} for t, c in enumerate(pattern) if c != " "]


@pytest.mark.skip("Part 4")
def test_session_timeline() -> None:
    """Uplink and downlink merge frame by frame, whatever the bursts, as soon as packets arrive."""
    uplink, downlink = packets("..vvv .vv."), packets("vvvv.. .vvvv")
    rows = [  # frame, user, model, overlap, barge_in
        (0, False, True, False, False),
        (1, False, True, False, False),
        (2, True, True, True, True),
        (3, True, True, True, False),
        (4, True, False, False, False),
        (5, None, False, False, False),
        (6, False, None, False, False),
        (7, True, False, False, False),
        (8, True, True, True, False),
        (9, False, True, False, False),
        (10, None, True, False, False),
        (11, None, True, False, False),
    ]
    expected = [
        {"frame": t, "ms": 80 * t, "user": u, "model": m, "overlap": o, "barge_in": b}
        for t, u, m, o, b in rows
    ]
    for up_sizes, down_sizes in (([9], [11]), ([1] * 9, [1] * 11), ([3, 0, 4, 2], [1, 5, 0, 5])):
        text = "".join(collect(timeline(bursts(uplink, up_sizes), bursts(downlink, down_sizes))))
        lines = [json.loads(line) for line in text.splitlines()]
        assert lines == expected, f"the same lines whatever the bursts, e.g. {up_sizes} and {down_sizes}"

    lost = "".join(collect(timeline(bursts(packets("v  v"), [1, 1]), bursts(packets(".  v"), [2]))))
    gap = [json.loads(line) for line in lost.splitlines()]
    assert [line["frame"] for line in gap] == [0, 1, 2, 3], "a frame both sides lost still gets its line"
    assert gap[3]["barge_in"], "a lost frame counts as not voiced"

    with pytest.raises(ValueError):
        collect(timeline(bursts(packets("vv")[::-1], [2]), bursts([], [])))
    with pytest.raises(ValueError):
        collect(timeline(bursts(packets("v") * 2, [1, 1]), bursts([], [])))

    pulled = {"up": 0, "down": 0}

    async def probe(side: str):
        for t in range(100):
            pulled[side] += 1
            await asyncio.sleep(0)
            yield [{"frame": t, "voiced": False}]

    async def first_line() -> str:
        agen = timeline(probe("up"), probe("down"))
        line = await agen.__anext__()
        await agen.aclose()
        return line

    assert json.loads(asyncio.run(first_line()))["frame"] == 0
    assert max(pulled.values()) <= 5, "send each frame's line as soon as both sides have it"


@pytest.mark.skip("Part 5")
def test_acoustic_delay() -> None:
    """Delayed codebooks move to later steps, and the layout undoes exactly."""
    U = UNSET
    frames = [
        {"text": 50 + t, "model": [10 * t + k for k in range(8)], "user": [100 + 10 * t + k for k in range(8)]}
        for t in range(3)
    ]
    steps = delay(frames, MOSHI_DELAYS)
    assert len(steps) == 4, "the last frame's acoustic codebooks need one more step"
    assert steps[0] == {"text": 50, "model": [0] + [U] * 7, "user": [100] + [U] * 7}, (
        "step 0 holds the semantic code of frame 0 and no acoustic codes"
    )
    assert steps[2] == {
        "text": 52,
        "model": [20, 11, 12, 13, 14, 15, 16, 17],
        "user": [120, 111, 112, 113, 114, 115, 116, 117],
    }, "step s holds the semantic code of frame s and the acoustic codes of frame s - 1"
    assert steps[3] == {
        "text": U,
        "model": [U, 21, 22, 23, 24, 25, 26, 27],
        "user": [U, 121, 122, 123, 124, 125, 126, 127],
    }, "the extra step holds only the last frame's acoustic codes"
    assert undelay(steps, MOSHI_DELAYS) == frames, "undelay gives the frames back exactly"
    assert ready_ms(0, MOSHI_DELAYS) == 160, "the floor: an 80 ms frame plus 80 ms of acoustic delay"
    assert ready_ms(9, MOSHI_DELAYS) == 880

    grouped = {"model": {"text": 0, "audio": [0, 2, 2]}, "user": {"audio": [0, 1, 1]}}
    session = [
        {"model": {"text": 5 + t, "audio": [t, 10 + t, 20 + t]}, "user": {"audio": [30 + t, 40 + t, 50 + t]}}
        for t in range(2)
    ]
    layout = delay(session, grouped)
    assert layout == [
        {"model": {"text": 5, "audio": [0, U, U]}, "user": {"audio": [30, U, U]}},
        {"model": {"text": 6, "audio": [1, U, U]}, "user": {"audio": [31, 40, 50]}},
        {"model": {"text": U, "audio": [U, 10, 20]}, "user": {"audio": [U, 41, 51]}},
        {"model": {"text": U, "audio": [U, 11, 21]}, "user": {"audio": [U, U, U]}},
    ], "streams can be grouped, and every codebook has its own delay"
    assert undelay(layout, grouped) == session
    assert ready_ms(0, grouped) == 240
    assert delay([], grouped) == [] and undelay([], grouped) == []

    with pytest.raises(ValueError):
        delay([{"text": 1, "model": [1] * 7, "user": [1] * 8}], MOSHI_DELAYS)
    with pytest.raises(ValueError):
        delay([{"text": 1, "model": [1] * 9, "user": [1] * 8}], MOSHI_DELAYS)
    with pytest.raises(ValueError):
        delay([{"text": 1, "model": [1] * 8, "user": [1] * 8, "extra": 1}], MOSHI_DELAYS)
    tampered = delay(frames, MOSHI_DELAYS)
    tampered[0]["model"][3] = 9
    with pytest.raises(ValueError):
        undelay(tampered, MOSHI_DELAYS)
    holed = delay(frames, MOSHI_DELAYS)
    holed[1]["model"][3] = UNSET
    with pytest.raises(ValueError):
        undelay(holed, MOSHI_DELAYS)
    with pytest.raises(ValueError):
        undelay(steps[:-1], MOSHI_DELAYS)
