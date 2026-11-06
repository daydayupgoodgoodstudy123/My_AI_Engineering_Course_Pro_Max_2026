import asyncio
import hashlib
import json
import math
import random
import time
from datetime import datetime, timedelta, timezone

import pytest
from provenance.alarm import watch_scores
from provenance.audit import AuditLog, Entry
from provenance.detector import FLOOR_DB, toy_detector_score
from provenance.localize import Segment, iou, locate
from provenance.manifest import TRAINED, Trace, manifest_hash, trace
from provenance.service import ProvenanceService

SR = 16000
UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))


def tone(freq: float, amp: float, n: int) -> list[float]:
    return [amp * math.sin(2.0 * math.pi * freq * i / SR) for i in range(n)]


@pytest.mark.skip("Part 1")
def test_spoof_detector() -> None:
    """The toy detector scores how much of a clip's energy sits at or above 4 kHz."""
    assert toy_detector_score(tone(6000, 0.1, 256), SR) > -1.0, "a clip of exactly one frame is scored"

    clip = tone(1000, 0.2, 256) + tone(6000, 0.1, 256)
    loud = toy_detector_score(clip, SR)
    assert loud == pytest.approx(10.0 * math.log10(0.2), abs=1e-6), (
        "a 6 kHz tone at half the amplitude of a 1 kHz tone carries a fifth of the energy"
    )
    assert toy_detector_score(tone(3000, 0.1, 256), SR) < -60.0, "a 3 kHz tone has nothing at or above 4 kHz"
    assert toy_detector_score(tone(4000, 0.1, 256), SR) > -3.0, "a 4 kHz tone sits at the cutoff, so it counts"

    assert toy_detector_score([0.0] * 256, SR) == FLOOR_DB, "silence scores the floor"
    assert toy_detector_score(tone(1000, 0.1, 256), SR) == FLOOR_DB, "the score is clipped at the floor"
    assert toy_detector_score([1e-4 * x for x in clip], SR) == pytest.approx(loud, rel=1e-9), (
        "the score does not change with playback volume"
    )
    assert toy_detector_score(clip + tone(6000, 0.5, 200), SR) == pytest.approx(loud, rel=1e-9), (
        "a trailing partial frame is dropped"
    )

    rng = random.Random(0)
    call = [rng.gauss(0.0, 0.1) for _ in range(256 * 8)]
    start = time.perf_counter()
    toy_detector_score(call, SR)
    assert time.perf_counter() - start < 0.1, "the detector should be fast"


@pytest.mark.skip("Part 2")
def test_audit_log(tmp_path) -> None:
    """Decisions are logged exactly as made, so an auditor can re-derive them after a reopen."""
    path = str(tmp_path / "audit.sqlite3")
    calibrated = 0.1 + 0.2  # straight out of a calibration sweep: 0.30000000000000004
    morning = datetime(2026, 3, 1, 9, 30, 0, 250_001, tzinfo=IST)
    log = AuditLog(path)
    first = log.record("clip-a", "toy-spectral 1.2", calibrated, 0.3, morning)
    second = log.record("clip-b", "toy-spectral 1.2", calibrated, calibrated, morning + timedelta(seconds=1))
    third = log.record("clip-c", "aasist 2.10", -1.25, 2.5, datetime(2026, 3, 2, 18, 45, tzinfo=UTC))
    assert (first.verdict, second.verdict) == ("bonafide", "spoof"), (
        "a score at or above the threshold is a spoof"
    )
    assert first.at.isoformat() == "2026-03-01T04:00:00.250001+00:00", "times come back in UTC"
    in_utc = datetime(2026, 3, 1, 4, 0, 0, 250_001, tzinfo=UTC)
    assert first == Entry(1, "clip-a", "toy-spectral 1.2", calibrated, 0.3, "bonafide", in_utc), (
        "a decision is logged exactly as made"
    )
    for score, threshold in ((math.nan, calibrated), (0.5, math.nan)):
        with pytest.raises(ValueError):
            log.record("clip-d", "toy-spectral 1.2", threshold, score, datetime(2026, 3, 2, tzinfo=UTC))
    with pytest.raises(ValueError):
        log.record("clip-d", "toy-spectral 1.2", calibrated, 0.5, datetime(2026, 3, 2, 9, 0))
    with pytest.raises(KeyError):
        log.get(4)
    log.close()

    reopened = AuditLog(path)
    assert reopened.entries() == [first, second, third], (
        "decisions survive a reopen exactly, in the order they were recorded"
    )
    assert reopened.entries(model="aasist 2.10") == [third], "filter by model"
    assert reopened.flips("toy-spectral 1.2", 0.3) == [first], (
        "a recalibrated threshold flips the decisions it moves across"
    )
    assert reopened.flips("aasist 2.10", 0.3) == [], "only that model's decisions are re-derived"
    reopened.close()


def speech(seconds: float, seed: int) -> list[float]:
    """A stand-in for recorded speech, the lesson's recipe: 220 and 440 Hz plus broadband noise."""
    rng = random.Random(seed)
    return [
        0.2 * math.sin(2.0 * math.pi * 220 * i / SR)
        + 0.08 * math.sin(2.0 * math.pi * 440 * i / SR)
        + rng.gauss(0.0, 0.02)
        for i in range(int(SR * seconds))
    ]


def generated(seconds: float, seed: int) -> list[float]:
    """A stand-in for TTS output, the lesson's recipe: 220 Hz, a flat 6 kHz line, almost no noise."""
    rng = random.Random(seed)
    return [
        0.2 * math.sin(2.0 * math.pi * 220 * i / SR)
        + 0.05 * math.sin(2.0 * math.pi * 6000 * i / SR)
        + rng.gauss(0.0, 0.002)
        for i in range(int(SR * seconds))
    ]


@pytest.mark.skip("Part 3")
def test_watermark_localization() -> None:
    """The watermarked part of a clip is located, however little of the clip it is."""
    probs = [0.2] * 100 + [0.9] * 150 + [0.5] * 10 + [0.8] * 90 + [0.5] * 150 + [0.1] * 250 + [0.7] * 250
    assert locate(probs, 1000) == [Segment(100, 350), Segment(750, 1000)], (
        "samples above the threshold, short gaps bridged, then short segments dropped"
    )
    edge = [0.9] * 60 + [0.0] * 20 + [0.9] * 40 + [0.0] * 21 + [0.9] * 100 + [0.0] * 5
    assert locate(edge, 1000) == [Segment(0, 120), Segment(141, 241)], (
        "a gap of exactly max_gap_s is bridged, and a segment of exactly min_s is kept"
    )

    assert iou([Segment(100, 350)], [Segment(150, 400)]) == pytest.approx(200 / 300)
    assert iou([Segment(0, 100), Segment(200, 300)], [Segment(50, 150), Segment(250, 350)]) == pytest.approx(
        100 / 300
    ), "IoU counts the samples the two lists share"
    assert iou([Segment(0, 300)], [Segment(0, 100), Segment(200, 300)]) == pytest.approx(200 / 300), (
        "one segment can overlap several in the other list"
    )
    assert iou([], []) == 1.0, "finding nothing where there is nothing is a perfect match"
    assert iou([Segment(0, 10)], []) == 0.0

    real, fake, more = speech(0.5, seed=1), generated(0.5, seed=2), speech(0.5, seed=3)
    rng = random.Random(4)
    probs = [rng.uniform(0.0, 0.4) for _ in real]
    probs += [rng.uniform(0.6, 1.0) for _ in fake]
    probs += [rng.uniform(0.0, 0.4) for _ in more]
    probs[3000:3040] = [0.95] * 40  # a 2.5 ms false alarm in the recorded speech
    probs[12000:12200] = [0.1] * 200  # the mark drowned out for 12.5 ms
    log = AuditLog()
    service = ProvenanceService(log, "toy-spectral 1.2", threshold=-18.0)
    when = datetime(2026, 3, 1, 4, 0, tzinfo=UTC)
    spliced = service.check("spliced", real + fake + more, probs, when)
    assert spliced.segments == [Segment(8000, 16000)], "the generated half second is located, end to end"
    assert spliced.entry.verdict == "spoof", "the spliced clip is scored and judged"
    assert log.get(spliced.entry.entry_id) == spliced.entry, "the decision is in the audit log"
    clean = service.check("clean", real + more, probs[:8000] + probs[16000:], when)
    assert (clean.entry.verdict, clean.segments) == ("bonafide", []), "recorded speech passes"


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


def split(items: list, sizes: list[int]) -> list[list]:
    """Cut items into consecutive batches, cycling through sizes (0 makes an empty batch)."""
    out, pos, i = [], 0, 0
    while pos < len(items):
        size = sizes[i % len(sizes)]
        out.append(items[pos : pos + size])
        pos += size
        i += 1
    return out


async def feed(items: list, sizes: list[int]):
    for batch in split(items, sizes):
        yield batch


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Split a Server-Sent Events stream into (event, data) pairs."""
    if not text:
        return []
    assert text.endswith("\n\n"), "every event ends with a blank line"
    events = []
    for block in text[:-2].split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((fields["event"], json.loads(fields["data"])))
    return events


CALL = [
    (0.5, 0.0), (1.0, 1.0), (1.5, 1.0), (2.0, 1.0), (2.5, 0.25), (3.0, 0.25),
    (3.5, 1.0), (4.0, 1.0), (4.5, 0.5), (5.0, 1.0), (5.5, 1.0), (6.0, 0.0),
    (8.0, 1.0), (8.5, 1.0),
]
ALARMS = [
    ("alarm", {"t": 1.5, "score": 0.75}),
    ("clear", {"t": 3.0, "peak": 0.875}),
    ("alarm", {"t": 5.0, "score": 0.837890625}),
    ("clear", {"t": 6.0, "peak": 0.9189453125}),
    ("alarm", {"t": 8.0, "score": 0.966217041015625}),
    ("clear", {"t": 8.5, "peak": 0.9831085205078125}),
]


@pytest.mark.skip("Part 4")
def test_spoof_alarm() -> None:
    """A live call's spoof scores become alarms as soon as each one is decided, whatever the batching."""
    for sizes in ([len(CALL)], [1], [2, 0, 3], [5, 0, 0, 1]):
        events = parse_sse("".join(collect(watch_scores(feed(CALL, sizes)))))
        assert events == ALARMS, f"same alarms whatever the batching, e.g. {sizes}"

    assert parse_sse("".join(collect(watch_scores(feed([(0.5, 1.0), (1.0, 0.75)], [1]))))) == [
        ("alarm", {"t": 0.5, "score": 1.0}),
        ("clear", {"t": 1.0, "peak": 1.0}),
    ], "the first score starts the average, and an alarm still open at the end clears there"
    assert parse_sse("".join(collect(watch_scores(feed([(0.5, 1.0), (1.0, 0.0), (1.5, 0.0)], [1]))))) == [
        ("alarm", {"t": 0.5, "score": 1.0}),
        ("clear", {"t": 1.5, "peak": 1.0}),
    ], "s exactly at clear_below keeps the alarm, and a cleared alarm is not cleared again"
    assert collect(watch_scores(feed([], [1]))) == [], "a call without scores raises nothing"
    for scores in ([(1.0, 0.1), (1.0, 0.2)], [(1.0, 0.1), (0.5, 0.2)]):
        with pytest.raises(ValueError):
            collect(watch_scores(feed(scores, [1])))

    pulled: list[int] = []

    async def probe():
        for i, batch in enumerate(split(CALL, [1])):
            pulled.append(i)
            yield batch

    async def first_event() -> str:
        agen = watch_scores(probe())
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert parse_sse(asyncio.run(first_event())) == ALARMS[:1]
    assert len(pulled) <= 3, "the alarm goes out as soon as the score that raises it arrives"


CAPTURE = "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"
RECORDED = {"action": "c2pa.created", "digitalSourceType": CAPTURE}


def credentials(generator: str, asset: bytes, action: dict, ingredients=()) -> dict:
    """A manifest for asset, with ingredients given as (relationship, label, that manifest).

    The manifest is None for an ingredient that came without content credentials.
    """
    assertions = [
        {"label": "c2pa.hash.data", "data": {"alg": "sha256", "hash": hashlib.sha256(asset).hexdigest()}},
        {"label": "c2pa.actions", "data": {"actions": [action]}},
    ]
    for relationship, label, manifest in ingredients:
        data = {"relationship": relationship, "title": label}
        if manifest is not None:
            data["manifest"] = {"url": label, "hash": manifest_hash(manifest)}
        assertions.append({"label": "c2pa.ingredient", "data": data})
    return {"claim_generator": generator, "assertions": assertions}


TAKE = credentials("field-recorder/3.0", b"interview take", RECORDED)
LINE = credentials("voice-tts/1.4", b"tts line", {"action": "c2pa.created", "digitalSourceType": TRAINED})
EDIT = credentials(
    "studio/2.1", b"edited interview", {"action": "c2pa.edited"},
    [("parentOf", "urn:take", TAKE), ("componentOf", "urn:line", LINE)],
)
MIX = credentials(
    "studio/2.1", b"final mix", {"action": "c2pa.edited"},
    [("componentOf", "urn:line", LINE), ("parentOf", "urn:edit", EDIT), ("componentOf", "music bed", None)],
)
STORE = {"urn:take": TAKE, "urn:line": LINE, "urn:edit": EDIT, "urn:mix": MIX}


@pytest.mark.skip("Part 5")
def test_manifest_chain() -> None:
    """Ingredient manifests are checked link by link, back to where the audio came from."""
    assert trace(STORE, "urn:mix", b"final mix") == Trace(["urn:mix", "urn:edit", "urn:take"], True, []), (
        "the history follows parentOf back to the recording, and the TTS line used twice counts"
    )
    assert trace(STORE, "urn:line", b"tts line") == Trace(["urn:line"], True, []), (
        "the asset's own manifest counts too"
    )
    assert trace(STORE, "urn:take", b"interview take") == Trace(["urn:take"], False, []), (
        "manifests the asset was not made from say nothing about it"
    )
    reencoded = trace(STORE, "urn:mix", b"final mix, re-encoded")
    assert reencoded.problems == ["urn:mix: assertion.dataHash.mismatch"], (
        "the active manifest is bound to the asset's bytes"
    )

    swapped = dict(STORE, **{"urn:take": credentials("field-recorder/3.0", b"another take", RECORDED)})
    assert trace(swapped, "urn:mix", b"final mix") == Trace(
        ["urn:mix", "urn:edit"], True, ["urn:edit: ingredient.hashedURI.mismatch"]
    ), "a changed ingredient manifest breaks the link to it, and the history stops there"
    stripped = {label: m for label, m in STORE.items() if label != "urn:line"}
    assert trace(stripped, "urn:mix", b"final mix") == Trace(
        ["urn:mix", "urn:edit", "urn:take"], False,
        ["urn:edit: ingredient.manifest.missing", "urn:mix: ingredient.manifest.missing"],
    ), "with the TTS manifest stripped, nothing left proves AI involvement"

    two = credentials(
        "studio/2.1", b"final mix", {"action": "c2pa.edited"},
        [("parentOf", "urn:edit", EDIT), ("parentOf", "urn:mix", MIX)],
    )
    assert trace(dict(stripped, **{"urn:two": two}), "urn:two", b"final mix") == Trace(
        ["urn:two"], False, [
            "urn:edit: ingredient.manifest.missing",
            "urn:mix: ingredient.manifest.missing",
            "urn:two: manifest.multipleParents",
        ],
    ), "a manifest with two parents has no single history, and a manifest reached twice is checked once"

    back = credentials("studio/2.1", b"b", {"action": "c2pa.edited"}, [("componentOf", "urn:a", {"draft": 1})])
    loop = credentials("studio/2.1", b"a", {"action": "c2pa.edited"}, [("parentOf", "urn:b", back)])
    with pytest.raises(ValueError):
        trace({"urn:a": loop, "urn:b": back}, "urn:a", b"a")
