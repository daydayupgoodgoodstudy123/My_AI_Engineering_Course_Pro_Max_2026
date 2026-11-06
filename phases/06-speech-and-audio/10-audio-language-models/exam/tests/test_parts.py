import asyncio
import copy
import time

import pytest
from lalmkit.context import AudioChunk, Turn, live_context
from lalmkit.inputs import (
    AUDIO,
    AUDIO_BOS,
    AUDIO_EOS,
    AUDIO_PAD,
    EOS,
    PAD,
    SAMPLE_RATE,
    assemble,
    audio_tokens,
    clip_tokens,
    expand,
    pad_batch,
)
from lalmkit.mcq import Item, parse_choice, score
from lalmkit.messages import Piece, flatten, usage
from lalmkit.results import Prediction, ResultStore
from lalmkit.service import BenchmarkRun


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def arrive(events: list):
    for event in events:
        yield event


def frames(n: int, start: int = 0) -> list[list[float]]:
    """Encoder output for a clip of n frames: each frame is [its number, 1.0]."""
    return [[float(start + i), 1.0] for i in range(n)]


EMBED = {token: [float(token)] * 3 for token in range(16)}
# A projector for frames stacked in pairs: [a, 1, b, 1] -> [a, b, how many real frames]
WEIGHTS = [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0]]


@pytest.mark.skip("Part 1")
def test_decoder_inputs() -> None:
    """Audio slots widen to exactly the projector's tokens, and a left-padded batch lines up."""
    assert clip_tokens(SAMPLE_RATE) == 25, "a second of audio is 50 frames, stacked in pairs"

    # a two-clip question, as in MMAU's multi-audio items: 5 frames and 2 frames
    ids, vectors = assemble([3, AUDIO, 4, AUDIO, 5], [frames(5), frames(2, start=10)], EMBED, WEIGHTS)
    assert ids == [
        3, AUDIO_BOS, AUDIO_PAD, AUDIO_PAD, AUDIO_PAD, AUDIO_EOS, 4, AUDIO_BOS, AUDIO_PAD, AUDIO_EOS, 5,
    ], "each AUDIO slot widens where it stands, to one AUDIO_PAD per audio token"
    assert vectors == [
        EMBED[3], EMBED[AUDIO_BOS], [0.0, 1.0, 2.0], [2.0, 3.0, 2.0], [4.0, 0.0, 1.0], EMBED[AUDIO_EOS],
        EMBED[4], EMBED[AUDIO_BOS], [10.0, 11.0, 2.0], EMBED[AUDIO_EOS], EMBED[5],
    ], "every audio token reaches the model, in order"
    assert [audio_tokens(n, stack=3) for n in (1, 2, 3, 4)] == [1, 1, 1, 2], (
        "a trailing partial run of frames is one more token"
    )

    # the second row is a two-turn prompt whose first turn ends with EOS
    batch, mask, positions = pad_batch([ids, [3, 4, EOS, 5]])
    assert batch == [ids, [PAD] * 7 + [3, 4, EOS, 5]], "generation pads on the left"
    assert mask == [[1] * 11, [0] * 7 + [1] * 4], "the mask hides the padding and nothing else"
    assert positions == [list(range(11)), [0] * 7 + [0, 1, 2, 3]], (
        "positions count each row's own tokens from 0; padding sits at 0"
    )

    call = expand([3, AUDIO, 4], [clip_tokens(600 * SAMPLE_RATE)])  # a ten-minute call recording
    start = time.perf_counter()
    pad_batch([call, [3, 4]])
    assert time.perf_counter() - start < 0.02, "pad_batch should be fast on a ten-minute clip"


@pytest.mark.skip("Part 2")
def test_result_store(tmp_path) -> None:
    """Raw outputs persist exactly, once per (model, item); a rerun replaces in place."""
    path = str(tmp_path / "results.sqlite3")
    raw = "  The answer is (B).\r\nA siren, then silence. \n"
    store = ResultStore(path)
    store.record("qwen2.5-omni-7b", "q-417", raw)
    store.record("qwen2.5-omni-7b", "q-052", None)  # the API call timed out
    store.record("qwen2.5-omni-7b", "q-139", "")  # the model answered with nothing
    store.record("gpt-4o-audio", "q-417", "C")
    store.close()

    reopened = ResultStore(path)
    assert reopened.predictions("qwen2.5-omni-7b") == [
        Prediction("qwen2.5-omni-7b", "q-417", raw),
        Prediction("qwen2.5-omni-7b", "q-052", None),
        Prediction("qwen2.5-omni-7b", "q-139", ""),
    ], "raw outputs round-trip exactly, in the order they were first recorded"
    pending = reopened.pending("qwen2.5-omni-7b", ["q-417", "q-052", "q-139", "q-008"])
    assert pending == ["q-052", "q-008"], "failed and missing calls are pending; an empty answer is an answer"

    reopened.record("qwen2.5-omni-7b", "q-052", "D")
    reopened.record("qwen2.5-omni-7b", "q-417", "B")
    assert [(p.item_id, p.output) for p in reopened.predictions("qwen2.5-omni-7b")] == [
        ("q-417", "B"),
        ("q-052", "D"),
        ("q-139", ""),
    ], "a rerun replaces the output and keeps the item's place"
    assert reopened.predictions("gpt-4o-audio") == [Prediction("gpt-4o-audio", "q-417", "C")], (
        "each model keeps its own predictions"
    )
    assert reopened.predictions("gemini-2.5-pro") == []
    reopened.close()


SCENE = ["Dog barking", "Siren", "Dog barking and a siren", "Silence"]

ITEMS = [
    Item("sp-1", "speech", "Is the caller upset?", ["Yes", "No"], "Yes"),
    Item("sp-2", "speech", "What does the caller want?",
         ["A refund", "A manager", "A callback", "Nothing"], "A refund"),
    Item("sp-3", "speech", "How many people speak?", ["One", "Two", "Three"], "Two"),
    Item("so-1", "sound", "What do you hear?", SCENE, "Dog barking and a siren"),
    Item("so-2", "sound", "What comes after the bark?", SCENE, "Silence"),
    Item("so-3", "sound", "Describe the scene.", None, "A dog barks at a passing ambulance."),
    Item("so-4", "sound", "Is it raining?", ["No"], "No"),
    Item("mu-1", "music", "Which instrument carries the melody?", ["Piano", "Violin", "Flute"], "Violin"),
    Item("mx-1", "multi", "Which clip is louder?", ["Audio 1", "Audio 2", "Same", "Can't tell"], "Audio 2"),
    Item("mx-2", "multi", "Which clip is faster?", ["Audio 1", "Audio 2", "Same", "Can't tell"], "Audio 1"),
    Item("mx-3", "multi", "Same speaker in both?", ["Yes", "No", "Only at the start", "Can't tell"], "No"),
    Item("mx-4", "multi", "Which clip has rain?", ["Audio 1", "Audio 2", "Both", "Neither"], "Both"),
]

OUTPUTS = {
    "sp-1": "Yes.",
    "sp-2": "(C) A callback",
    "sp-3": "Two people are talking.",
    "so-1": "dog barking and a siren.",
    "so-3": "A dog barks at an ambulance.",
    "so-4": "No",
    "mu-1": "The violin carries it, so B.",
    "mx-1": "Audio 2 is louder (B).",
    "mx-2": "(A) or (C)",
    "mx-3": None,
    "mx-4": "A",
}


@pytest.mark.skip("Part 3")
def test_score_multiple_choice() -> None:
    """Free-text answers map to a choice, and accuracy is reported per category next to chance."""
    assert parse_choice("(B)", SCENE) == 1, "a letter names a choice"
    assert parse_choice("Answer: C\n", SCENE) == 2
    assert parse_choice("A dog barks at a siren, so B.", SCENE) == 1, "a word like 'A' is not an answer letter"
    assert parse_choice("dog barking and a siren.", SCENE) == 2, "an answer can be the full text of one choice"
    assert parse_choice("(D). Final answer: D", SCENE) == 3, "naming one choice twice still picks it"
    assert parse_choice("(A) or (C)", SCENE) is None, "an answer that names two choices picks neither"
    assert parse_choice("(C)", ["Yes", "No"]) is None, "a letter past the last choice picks nothing"
    assert parse_choice(None, SCENE) is None

    report = score(ITEMS, OUTPUTS)
    assert report["count"] == {"speech": 3, "sound": 2, "music": 1, "multi": 4}, (
        "only items with at least two choices are scored"
    )
    assert report["accuracy"] == pytest.approx(
        {"speech": 1 / 3, "sound": 0.5, "music": 1.0, "multi": 0.25}
    ), "missing, failed and unreadable answers count as wrong"
    assert report["chance"] == pytest.approx(
        {"speech": (1 / 2 + 1 / 4 + 1 / 3) / 3, "sound": 0.25, "music": 1 / 3, "multi": 0.25}
    ), "chance depends on how many choices each item has"
    assert report["overall"] == pytest.approx(0.4), "overall averages the scored items"
    assert report["macro"] == pytest.approx((1 / 3 + 0.5 + 1.0 + 0.25) / 4), (
        "macro averages the categories, not the items"
    )

    run = BenchmarkRun(ResultStore(), ITEMS)
    asked: list[str] = []

    def ask(item: Item) -> str:
        asked.append(item.item_id)
        if item.item_id == "mx-3" and asked.count("mx-3") == 1:
            raise TimeoutError("the audio API timed out")
        return OUTPUTS.get(item.item_id) or ""

    assert run.run("qwen2.5-omni-7b", ask) == len(ITEMS)
    assert run.run("qwen2.5-omni-7b", ask) == 1, "a rerun asks again only for the call that failed"
    assert run.report("qwen2.5-omni-7b") == report, "the stored outputs score the same"


def clip(n: int) -> list[int]:
    return [AUDIO_BOS] + [AUDIO_PAD] * n + [AUDIO_EOS]


SYSTEM = Turn("system", [1, 2, 3, 4])


@pytest.mark.skip("Part 4")
def test_live_context() -> None:
    """The context keeps the turns and the newest audio within the budget, as events arrive."""
    for chunks in ([16000], [1000] * 16, [5, 315, 0, 9680, 6000]):  # one second of audio, chunked
        events = [
            SYSTEM,
            *[AudioChunk(n) for n in chunks],
            Turn("user", [20, 21, 22]),
            Turn("assistant", [30, 31]),
            AudioChunk(8000),
            Turn("user", [23, 24]),
        ]
        contexts = collect(live_context(arrive(events), budget=40))
        assert len(contexts) == len(events), "one context per event"
        assert contexts[0] == [1, 2, 3, 4], "each context is the state when its event arrived"
        assert contexts[len(chunks)] == [1, 2, 3, 4] + clip(25), (
            f"consecutive chunks are one clip, whatever the chunking, e.g. {chunks[:6]}"
        )
        assert all(len(ids) <= 40 for ids in contexts), "a context never exceeds the budget"
        assert contexts[-1] == [1, 2, 3, 4] + clip(12) + [20, 21, 22, 30, 31] + clip(13) + [23, 24], (
            "the oldest audio goes first, token by token from the front of the oldest clip"
        )

    events = [
        SYSTEM,
        AudioChunk(640),
        Turn("user", [20, 21, 22]),
        Turn("assistant", [30, 31]),
        Turn("user", [23, 24, 25]),
    ]
    contexts = collect(live_context(arrive(events), budget=10))
    assert contexts[3] == [1, 2, 3, 4, 20, 21, 22, 30, 31], (
        "a clip that loses all its tokens goes with its markers"
    )
    assert contexts[4] == [1, 2, 3, 4, 30, 31, 23, 24, 25], (
        "turns go only once no audio is left: oldest first, never the system turn"
    )
    events = [SYSTEM, Turn("user", [20, 21, 22, 23, 24]), Turn("assistant", [30, 31]), AudioChunk(640)]
    assert collect(live_context(arrive(events), budget=10))[-1] == [1, 2, 3, 4, 30, 31] + clip(1), (
        "a dropped turn stays dropped, and new audio can use its room"
    )
    with pytest.raises(ValueError):
        collect(live_context(arrive([SYSTEM, Turn("user", list(range(20, 27)))]), budget=10))

    pulled: list[int] = []

    async def microphone():
        for i in range(100):
            pulled.append(i)
            yield AudioChunk(320)

    async def first_context() -> list[int]:
        agen = live_context(microphone(), budget=40)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert asyncio.run(first_context()) == clip(1)
    assert len(pulled) == 1, "a context is ready as soon as its event arrives"
    assert collect(live_context(microphone(), budget=40))[-1] == clip(38), (
        "a clip still being recorded loses its oldest tokens too"
    )


def silence(seconds: float) -> list[float]:
    return [0.0] * round(seconds * SAMPLE_RATE)


CALL = [
    {"role": "system", "content": "You audit bank calls."},
    {"role": "user", "content": [
        {"type": "audio", "audio": silence(0.5), "sampling_rate": 16000},
        {"type": "text", "text": "Did the agent read the disclosure?"},
    ]},
    {"role": "assistant", "content": "Splitting the speakers first."},
    {"role": "tool", "content": [
        {"type": "tool_result", "tool_call_id": "diarize-1", "content": [
            {"type": "text", "text": "agent:"},
            {"type": "tool_result", "tool_call_id": "cut-1", "content": [
                {"type": "audio", "audio": silence(0.3), "sampling_rate": 16000},
                {"type": "text", "text": "we must tell you this call is recorded"},
            ]},
            {"type": "text", "text": "customer:"},
            {"type": "audio", "audio": silence(0.1), "sampling_rate": 16000},
        ]},
    ]},
    {"role": "user", "content": [
        {"type": "audio", "audio": silence(0.02), "sampling_rate": 16000},
        {"type": "tool_result", "tool_call_id": "note-1", "content": "and this clip?"},
    ]},
]


@pytest.mark.skip("Part 5")
def test_flatten_messages() -> None:
    """Nested messages flatten in reading order, clips are numbered across the call, bad parts say where."""
    expected = [
        Piece("system", "text", "You audit bank calls.", 4),
        Piece("user", "audio", "Audio 1", 13),
        Piece("user", "text", "Did the agent read the disclosure?", 6),
        Piece("assistant", "text", "Splitting the speakers first.", 4),
        Piece("tool", "text", "agent:", 1),
        Piece("tool", "audio", "Audio 2", 8),
        Piece("tool", "text", "we must tell you this call is recorded", 8),
        Piece("tool", "text", "customer:", 1),
        Piece("tool", "audio", "Audio 3", 3),
        Piece("user", "audio", "Audio 4", 1),
        Piece("user", "text", "and this clip?", 3),
    ]
    pieces = flatten(CALL)
    order = [(p.role, p.kind, p.text) for p in expected]
    assert [(p.role, p.kind, p.text) for p in pieces] == order, (
        "pieces come out in reading order; clips are numbered across the call"
    )
    assert pieces == expected, "a text piece counts its words, a clip its audio tokens"
    assert flatten(CALL) == expected, "flattening twice gives the same pieces"
    assert usage(CALL) == {"text": 27, "audio": 25}, "tokens are counted per modality"

    resampled = copy.deepcopy(CALL)
    resampled[3]["content"][0]["content"][1]["content"][0]["sampling_rate"] = 44100
    with pytest.raises(ValueError, match=r"^messages\[3\]\.content\[0\]\.content\[1\]\.content\[0\]"):
        flatten(resampled)
    imaged = copy.deepcopy(CALL)
    imaged[1]["content"].append({"type": "image", "image": "spectrogram.png"})
    with pytest.raises(ValueError, match=r"^messages\[1\]\.content\[2\]"):
        flatten(imaged)
    with pytest.raises(ValueError, match=r"^messages\[0\]\.content\[0\]"):
        flatten([{"role": "user", "content": [{"type": "audio", "audio": [], "sampling_rate": 16000}]}])
    with pytest.raises(ValueError, match=r"^messages\[0\]"):
        flatten([{"role": "narrator", "content": "hello"}])
