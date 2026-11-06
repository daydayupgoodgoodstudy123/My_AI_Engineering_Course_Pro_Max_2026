import asyncio
import json
import math
import random
import time

import pytest
from cliptag.bank import Clip, ClipBank
from cliptag.classify import classify, evaluate
from cliptag.features import featurize, frame_signal, summarize
from cliptag.service import TaggingService
from cliptag.stream import stream_labels
from cliptag.taxonomy import rollup


def tone(freq: float, sr: int, seconds: float, seed: int = 0) -> list[float]:
    """A noisy sine, the same recipe as the lesson's synthetic dataset."""
    rng = random.Random(seed)
    return [
        0.5 * math.sin(2.0 * math.pi * freq * i / sr) + rng.gauss(0.0, 0.05)
        for i in range(int(sr * seconds))
    ]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def chunked(signal: list[float], sizes: list[int]):
    pos = 0
    for size in sizes:
        yield signal[pos : pos + size]
        pos += size


@pytest.mark.skip("Part 1")
def test_feature_pipeline() -> None:
    """The MFCC pipeline must be correct, fast and numerically stable."""
    sr = 2000
    assert frame_signal(list(range(10)), 4, 3) == [
        [0, 1, 2, 3],
        [3, 4, 5, 6],
        [6, 7, 8, 9],
    ], "frames are hop samples apart"

    # 60 samples is shorter than one 128-sample frame: there is nothing to summarize
    with pytest.raises(ValueError):
        summarize(featurize(tone(300, sr, 0.03), sr))

    assert summarize([[1.0, 10.0], [3.0, 30.0]]) == [2.0, 20.0, 1.0, 100.0], (
        "pool the mean, then the population variance, over time"
    )
    assert summarize([[1.0, 2.0]]) == [1.0, 2.0, 0.0, 0.0], "a one-frame clip is valid"

    rng = random.Random(0)
    long_clip = [[rng.gauss(0.0, 1.0) for _ in range(13)] for _ in range(3000)]
    start = time.perf_counter()
    summarize(long_clip)
    assert time.perf_counter() - start < 0.2, "summarize should be fast on long clips"

    offset = [[1e8 + d, -1e8 - d] for d in (0.0, 1.0, 2.0, 3.0)]
    variances = summarize(offset)[2:]
    assert all(math.isclose(v, 1.25, rel_tol=1e-9) for v in variances), (
        "variance must stay accurate when features carry a large offset"
    )


@pytest.mark.skip("Part 2")
def test_bank_roundtrip(tmp_path) -> None:
    """Clips survive a round trip through the bank, including a reopen."""
    path = str(tmp_path / "bank.sqlite3")
    tricky = [0.1 + 0.2, 1 / 3, 2.5e-310, -1e300, 0.0]

    bank = ClipBank(path)
    first = bank.add("dog", "train", 8000, tricky)
    second = bank.add("siren", "eval", 8000, [1.0, 2.0, 3.0, 4.0, 5.0])
    assert isinstance(first, str) and first != second, "add returns a new id for every clip"
    assert bank.get(first) == Clip(first, "dog", "train", 8000, tricky), (
        "a clip must round-trip exactly"
    )
    with pytest.raises(KeyError):
        bank.get("no-such-clip")
    bank.close()

    reopened = ClipBank(path)
    assert [c.clip_id for c in reopened.clips()] == [first, second], (
        "a reopened bank sees earlier clips, in insertion order"
    )
    assert [c.label for c in reopened.clips(split="eval")] == ["siren"], "filter by split"
    with pytest.raises(ValueError):
        reopened.add("dog", "test", 8000, tricky)
    with pytest.raises(ValueError):
        reopened.add("dog", "train", 8000, [1.0, 2.0])
    with pytest.raises(ValueError):
        reopened.add("dog", "train", 16000, tricky)
    reopened.close()


@pytest.mark.skip("Part 3")
def test_classify_and_evaluate() -> None:
    """Tag clips with k-NN, then report per-class quality on an imbalanced eval split."""
    bank = ClipBank()
    for vec in ([1.0, 0.1], [1.0, 0.2], [0.9, 0.0]):
        bank.add("dog", "train", 8000, vec)
    for vec in ([0.1, 1.0], [0.0, 0.9], [0.2, 1.0]):
        bank.add("siren", "train", 8000, vec)
    assert classify(bank, [0.05, 1.0], k=3) == "siren", "the most similar clips decide"
    bank.add("siren", "eval", 8000, [1.0, 0.3])
    assert classify(bank, [1.0, 0.3], k=1) == "dog", "classify only searches the train split"

    tie = ClipBank()
    for label, vec in (("a", [1.0, 0.14]), ("b", [1.0, 0.2]), ("b", [1.0, 0.25]), ("a", [1.0, 1.7])):
        tie.add(label, "train", 8000, vec)
    assert classify(tie, [1.0, 0.0], k=4) == "b", "a 2-2 vote goes to the larger summed similarity"

    for i in range(7):
        bank.add("dog", "eval", 8000, [1.0, 0.01 * i])
    bank.add("dog", "eval", 8000, [0.95, 0.0])
    bank.add("siren", "eval", 8000, [0.9, 0.4])
    report = evaluate(bank, k=3)
    assert report["accuracy"] == pytest.approx(0.8)
    assert report["recall"] == {"dog": 1.0, "siren": 0.0}, "recall is reported per class"
    assert report["macro_f1"] == pytest.approx((16 / 18 + 0.0) / 2), (
        "macro F1 counts the class the model never predicts"
    )

    service = TaggingService(ClipBank(), sample_rate=2000)
    for seed in range(3):
        service.register("low", "train", tone(150, 2000, 0.25, seed=seed))
        service.register("high", "train", tone(600, 2000, 0.25, seed=10 + seed))
    assert service.tag(tone(150, 2000, 0.25, seed=99)) == "low", "tag real audio end to end"
    assert service.tag(tone(600, 2000, 0.25, seed=98)) == "high", "tag real audio end to end"


@pytest.mark.skip("Part 4")
def test_stream_labels() -> None:
    """Windows are labeled as the stream arrives, whatever the chunk sizes."""
    sr = 100
    signal = [0.0] * 60 + [1.0] * 50
    seen: list[list[float]] = []

    def loudness(samples: list[float]) -> str:
        seen.append(samples)
        return "loud" if sum(abs(s) for s in samples) / len(samples) > 0.5 else "quiet"

    expected = [
        {"start": 0.0, "end": 0.5, "label": "quiet"},
        {"start": 0.25, "end": 0.75, "label": "quiet"},
        {"start": 0.5, "end": 1.0, "label": "loud"},
    ]
    for sizes in ([110], [1] * 110, [7, 0, 30, 2, 50, 21]):
        seen.clear()
        text = "".join(collect(stream_labels(chunked(signal, sizes), sr, loudness)))
        events = [json.loads(line) for line in text.splitlines()]
        assert events == expected, f"same events whatever the chunking, e.g. {sizes[:6]}"
        assert seen == [signal[0:50], signal[25:75], signal[50:100]], (
            "each window is exactly 0.5 s of the stream"
        )

    pulled: list[int] = []

    async def probe():
        for i in range(100):
            pulled.append(i)
            yield [0.0] * 10

    async def first_event() -> str:
        agen = stream_labels(probe(), sr, loudness)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert json.loads(asyncio.run(first_event()))["start"] == 0.0
    assert len(pulled) <= 6, "emit each window as soon as it is complete"


ONTOLOGY = {
    "Animal": {
        "Domestic animals": {"Dog": ["Bark", "Howl"], "Cat": ["Meow", {"Purr": []}]},
        "Wild animals": ["Roar"],
    },
    "Human sounds": ["Speech", "Whistling"],
    "Sounds of things": {"Alarm": ["Siren", "Whistling"], "Vehicle": {"Car": ["Horn"]}},
}


@pytest.mark.skip("Part 5")
def test_ontology_rollup() -> None:
    """Scores roll up to every ancestor, through nested dicts and lists."""
    assert rollup({"Bark": 0.9, "Meow": 0.2, "Purr": 0.4, "Siren": 0.7}, ONTOLOGY) == {
        "Bark": 0.9,
        "Dog": 0.9,
        "Meow": 0.2,
        "Purr": 0.4,
        "Cat": 0.4,
        "Domestic animals": 0.9,
        "Animal": 0.9,
        "Siren": 0.7,
        "Alarm": 0.7,
        "Sounds of things": 0.7,
    }, "a parent takes the max score below it; unscored branches are left out"
    assert rollup({"Whistling": 0.6}, ONTOLOGY) == {
        "Whistling": 0.6,
        "Human sounds": 0.6,
        "Alarm": 0.6,
        "Sounds of things": 0.6,
    }, "a class with two parents reaches both"
    assert rollup({"Dog": 0.95, "Bark": 0.3}, ONTOLOGY) == {
        "Dog": 0.95,
        "Bark": 0.3,
        "Domestic animals": 0.95,
        "Animal": 0.95,
    }, "a class keeps its own score when it beats its children"
    with pytest.raises(ValueError):
        rollup({"Moo": 0.5}, ONTOLOGY)
    with pytest.raises(ValueError):
        rollup({"Dog": 0.5}, {"Dog": {"Puppy": ["Dog"]}})
