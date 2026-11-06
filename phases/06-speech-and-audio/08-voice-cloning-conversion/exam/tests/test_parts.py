import asyncio
import json
import math
import random
import time
from datetime import datetime, timedelta, timezone

import pytest
from clonegate.consent import Consent, ConsentRegistry
from clonegate.knnvc import cosine, knn_convert
from clonegate.monitor import watch
from clonegate.policy import Decision, Request, evaluate
from clonegate.service import CloneGate
from clonegate.watermark import Watermarker, bit_accuracy, int_to_bits

KEY = 20260422
SR = 16000
IST = timezone(timedelta(hours=5, minutes=30))
JST = timezone(timedelta(hours=9))
UTC = timezone.utc


def speech(seconds: float, seed: int) -> list[float]:
    """A stand-in for rendered speech: four harmonics of a random pitch, plus a little noise."""
    rng = random.Random(seed)
    f0 = rng.uniform(90.0, 220.0)
    phases = [rng.uniform(0.0, 2.0 * math.pi) for _ in range(4)]
    return [
        sum(0.03 / (h + 1) * math.sin(2.0 * math.pi * f0 * (h + 1) * i / SR + phases[h]) for h in range(4))
        + rng.gauss(0.0, 0.01)
        for i in range(int(SR * seconds))
    ]


def pieces(audio: list[float], sizes: list[int]) -> list[list[float]]:
    """Cut audio into chunks, cycling through sizes (0 makes an empty chunk)."""
    out, pos, i = [], 0, 0
    while pos < len(audio):
        size = sizes[i % len(sizes)]
        out.append(audio[pos : pos + size])
        pos += size
        i += 1
    return out


@pytest.mark.skip("Part 1")
def test_watermark_roundtrip() -> None:
    """Stamped clips can be verified later, from the audio alone, by anyone holding the key."""
    stamper = Watermarker(KEY)
    host_a, host_b = speech(2.0, seed=1), speech(2.0, seed=2)
    first = stamper.embed(host_a, int_to_bits(1, 16))
    second = stamper.embed(host_b, int_to_bits(2, 16))
    assert max(abs(m - h) for m, h in zip(second, host_b)) <= 1.0001 * stamper.strength, "the mark is small"

    verifier = Watermarker(KEY)
    for clip, consent_id in ((second, 2), (first, 1)):
        assert verifier.detect(clip).bits == int_to_bits(consent_id, 16), (
            "a separate verifier with the same key reads every stamped clip"
        )

    normal = verifier.detect(first)
    quiet = verifier.detect([0.1 * x for x in first])
    assert quiet.scores == pytest.approx(normal.scores), "scores do not change with playback volume"
    assert normal.found and quiet.found, "a stamped clip is found"
    assert not verifier.detect(host_a).found, "unstamped audio carries no mark"
    assert not Watermarker(KEY + 1).detect(first).found, "only the right key finds the mark"

    assert bit_accuracy([1, 0, 1, 1], [1, None, 1, 0]) == 0.5, "a bit without evidence counts as wrong"
    assert bit_accuracy([1, 0], [None, None]) == 0.0, "a bit without evidence counts as wrong"

    chunks = pieces(second, [101, 59, 160, 0, 3, 77])
    evidence = verifier.evidence()
    start = time.perf_counter()
    for chunk in chunks:
        evidence.add(chunk)
    elapsed = time.perf_counter() - start
    assert verifier.verdict(evidence).scores == pytest.approx(verifier.detect(second).scores), (
        "evidence fed in chunks matches evidence fed at once"
    )
    assert elapsed < 0.05, "evidence should be quick to update as a stream arrives"

    one, two = verifier.evidence(), verifier.evidence()
    for a, b in zip(pieces(first, [4000]), pieces(second, [4000])):
        one.add(a)
        two.add(b)
    assert [verifier.verdict(e).bits for e in (one, two)] == [int_to_bits(1, 16), int_to_bits(2, 16)], (
        "two streams can be checked at the same time"
    )


@pytest.mark.skip("Part 2")
def test_consent_registry(tmp_path) -> None:
    """Consents survive a reopen exactly as signed, and stop at the right moment."""
    path = str(tmp_path / "consents.sqlite3")
    signed = datetime(2026, 4, 22, 1, 15, 30, 250_001, tzinfo=IST)
    registry = ConsentRegistry(path)
    rohit = registry.grant("rohit", {"dubbing", "assistive"}, signed, datetime(2027, 4, 22, tzinfo=IST))
    aiko = registry.grant(
        "aiko", {"dubbing"}, datetime(2026, 4, 30, 9, 0, tzinfo=JST), datetime(2026, 5, 1, tzinfo=JST)
    )
    assert (rohit.consent_id, aiko.consent_id) == (1, 2), "ids are small integers, issued in order"
    assert registry.get(1) == Consent(
        1, "rohit", frozenset({"dubbing", "assistive"}), signed, datetime(2027, 4, 22, tzinfo=IST)
    ), "a consent round-trips"
    with pytest.raises(KeyError):
        registry.get(3)
    with pytest.raises(ValueError):
        registry.grant("mei", {"dubbing"}, datetime(2026, 5, 1, 9, 0), datetime(2027, 5, 1, 9, 0))
    with pytest.raises(ValueError):
        registry.grant("mei", {"dubbing"}, datetime(2027, 5, 1, tzinfo=JST), datetime(2026, 5, 1, tzinfo=JST))
    registry.close()

    reopened = ConsentRegistry(path)
    stored = reopened.get(1)
    assert stored == rohit, "consents survive a reopen"
    assert stored.granted_at.isoformat() == "2026-04-22T01:15:30.250001+05:30", (
        "times come back exactly as signed, offset included"
    )
    assert reopened.active("aiko", "dubbing", datetime(2026, 4, 29, 23, 59, tzinfo=UTC)) == [], (
        "not valid before it is granted"
    )
    assert reopened.active("aiko", "dubbing", datetime(2026, 4, 30, 14, 59, tzinfo=UTC)) == [aiko], (
        "valid until it expires"
    )
    assert reopened.active("aiko", "dubbing", datetime(2026, 4, 30, 15, 0, tzinfo=UTC)) == [], (
        "a consent expires at a moment in time, whatever the offset"
    )
    assert reopened.active("rohit", "ads", datetime(2026, 5, 1, tzinfo=UTC)) == [], "a purpose out of scope"
    reopened.revoke(1, datetime(2026, 6, 1, 12, 0, tzinfo=UTC))
    reopened.revoke(1, datetime(2026, 7, 1, 12, 0, tzinfo=UTC))
    reopened.close()

    again = ConsentRegistry(path)
    assert again.get(1).revoked_at.isoformat() == "2026-06-01T12:00:00+00:00", (
        "revocation is permanent and keeps its first time"
    )
    assert again.active("rohit", "dubbing", datetime(2026, 6, 1, 11, 59, tzinfo=UTC)) == [again.get(1)], (
        "valid until it is revoked"
    )
    assert again.active("rohit", "dubbing", datetime(2026, 6, 1, 12, 0, tzinfo=UTC)) == [], (
        "revoked from that moment on"
    )
    with pytest.raises(ValueError):
        again.active("rohit", "dubbing", datetime(2026, 5, 1, 12, 0))
    again.close()


PHONES = "aeiou"
DIM = 12


def unit(name: str) -> list[float]:
    rng = random.Random(name)
    v = [rng.gauss(0.0, 1.0) for _ in range(DIM)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


CONTENT = {p: unit(f"phone {p}") for p in PHONES}
VOICE = {s: unit(f"speaker {s}") for s in ("alice", "bob")}


def utter(speaker: str, phones: str, seed: int) -> list[list[float]]:
    """Toy WavLM frames: the phone's content vector, a weaker speaker vector, and noise."""
    rng = random.Random(seed)
    return [
        [c + 0.5 * v + rng.gauss(0.0, 0.05) for c, v in zip(CONTENT[p], VOICE[speaker])]
        for p in phones
    ]


def closest(vec: list[float], table: dict[str, list[float]]) -> str:
    return max(table, key=lambda name: cosine(vec, table[name]))


def voice_of(frames: list[list[float]]) -> str:
    """Toy speaker probe: what is left of the frames once their phones are taken out."""
    rest = [0.0] * DIM
    for frame in frames:
        content = CONTENT[closest(frame, CONTENT)]
        rest = [r + f - c for r, f, c in zip(rest, frame, content)]
    return closest(rest, VOICE)


@pytest.mark.skip("Part 3")
def test_convert_with_consent() -> None:
    """kNN-VC puts bob's words in alice's voice, using only audio alice consented to."""
    matching = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.5], [0.5, 1.0]]
    assert knn_convert([[1.0, 0.3], [0.2, 1.0]], matching, k=1) == [[1.0, 0.5], [0.0, 1.0]], (
        "each frame becomes its nearest matching frame"
    )
    assert knn_convert([[1.0, 0.3], [0.2, 1.0]], matching, k=2) == [[1.0, 0.25], [0.25, 1.0]], (
        "each frame becomes the mean of its k nearest matching frames"
    )
    assert knn_convert([[1.0, 0.2]], [[4.0, 0.8], [1.0, 0.6]], k=1) == [[4.0, 0.8]], (
        "nearest by cosine distance, so loudness does not matter"
    )
    assert knn_convert([[2.0, 0.5]], [[4.0, 0.0], [1.0, 0.0], [0.0, 1.0]], k=1) == [[4.0, 0.0]], (
        "ties go to the frame that comes first in the matching set"
    )
    for k in (0, 5):
        with pytest.raises(ValueError):
            knn_convert([[1.0, 0.0]], matching, k=k)

    t0 = datetime(2026, 4, 22, 9, 0, tzinfo=IST)
    registry = ConsentRegistry()
    alice = registry.grant("alice", {"dubbing"}, t0, t0 + timedelta(days=365))
    alice_ads = registry.grant("alice", {"ads", "dubbing"}, t0, t0 + timedelta(days=365))
    bob = registry.grant("bob", {"dubbing"}, t0, t0 + timedelta(days=365))
    gate = CloneGate(registry, Watermarker(KEY))
    pool = utter("alice", PHONES * 4, seed=1)
    gate.enroll(alice.consent_id, pool)
    gate.enroll(alice_ads.consent_id, utter("alice", PHONES * 4, seed=2))
    gate.enroll(bob.consent_id, utter("bob", PHONES * 4, seed=3))

    source = utter("bob", "oiaeuaio", seed=4)
    when = t0 + timedelta(days=30)
    result = gate.convert(source, alice.consent_id, "dubbing", when)
    assert result.frames == knn_convert(source, pool, k=4), (
        "the matching set is the audio enrolled under this consent, nothing else"
    )
    assert [closest(f, CONTENT) for f in result.frames] == list("oiaeuaio"), "the words are bob's"
    assert (voice_of(source), voice_of(result.frames)) == ("bob", "alice"), "the voice is alice's"

    with pytest.raises(PermissionError):
        gate.convert(source, alice.consent_id, "ads", when)
    with pytest.raises(PermissionError):
        gate.convert(source, alice.consent_id, "dubbing", t0 + timedelta(days=365))
    registry.revoke(alice.consent_id, when + timedelta(days=1))
    with pytest.raises(PermissionError):
        gate.convert(source, alice.consent_id, "dubbing", when + timedelta(days=2))

    rendered = speech(2.0, seed=5)
    assert gate.trace(gate.stamp(rendered, result.consent_id)) == registry.get(alice.consent_id), (
        "a stamped conversion traces back to its consent"
    )
    assert gate.trace(rendered) is None, "unstamped audio traces to nothing"


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def chunked(audio: list[float], sizes: list[int]):
    for piece in pieces(audio, sizes):
        yield piece


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Split a Server-Sent Events stream into (event, data) pairs."""
    assert text.endswith("\n\n"), "every event ends with a blank line"
    events = []
    for block in text[:-2].split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.mark.skip("Part 4")
def test_watch_stream() -> None:
    """A live stream gets exactly one verdict, as soon as the evidence allows."""
    wm = Watermarker(KEY)
    call = wm.embed(speech(3.0, seed=6), int_to_bits(0x2026, 16))
    for sizes in ([len(call)], [1], [160], [999, 0, 7, 1601, 333]):
        events = parse_sse("".join(collect(watch(chunked(call, sizes), wm, SR))))
        assert len(events) == 1, "exactly one verdict per stream"
        assert events == [("watermark", {"payload": 0x2026, "at": 1.1})], (
            f"same verdict whatever the chunking, e.g. {sizes}"
        )

    cut = call[: int(SR * 1.05)]
    assert parse_sse("".join(collect(watch(chunked(cut, [500]), wm, SR)))) == [
        ("watermark", {"payload": 0x2026, "at": 1.05})
    ], "the end of the stream is scored too"
    plain = speech(1.03, seed=7)
    assert parse_sse("".join(collect(watch(chunked(plain, [700]), wm, SR)))) == [
        ("unmarked", {"seconds": 1.03})
    ], "a stream without a mark ends unmarked"
    assert parse_sse("".join(collect(watch(chunked([], [1]), wm, SR)))) == [("unmarked", {"seconds": 0.0})]

    pulled: list[int] = []

    async def probe():
        for i, piece in enumerate(pieces(call, [400])):
            pulled.append(i)
            yield piece

    async def first_event() -> str:
        agen = watch(probe(), wm, SR)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert parse_sse(asyncio.run(first_event()))[0][0] == "watermark"
    assert len(pulled) <= 44, "the verdict comes as soon as the evidence is in"
    pulled.clear()
    collect(watch(probe(), wm, SR))
    assert len(pulled) <= 44, "no more audio is read after the verdict"


ROHIT = {
    "all": [
        {"purpose": ["dubbing", "assistive"]},
        {"not": {"region": ["US"]}},
        {
            "any": [
                {"until": "2027-04-22T00:00:00+05:30"},
                {"all": [{"purpose": ["assistive"]}, {"until": "2036-04-22T00:00:00+05:30"}]},
            ]
        },
    ]
}


@pytest.mark.skip("Part 5")
def test_policy_decisions() -> None:
    """Nested consent policies allow or deny a request, and say which rule said no."""
    may = datetime(2026, 5, 1, 10, 0, tzinfo=IST)
    later = datetime(2028, 1, 1, tzinfo=IST)
    assert evaluate(ROHIT, Request("dubbing", "IN", may)) == Decision(True), "every rule allows"
    assert evaluate(ROHIT, Request("ads", "IN", may)) == Decision(False, "/all/0"), (
        "the first rule of an all that denies is the rule that denies"
    )
    assert evaluate(ROHIT, Request("dubbing", "US", may)) == Decision(False, "/all/1"), (
        "a not whose rule allows is the rule that denies"
    )
    assert evaluate(ROHIT, Request("dubbing", "IN", later)) == Decision(False, "/all/2"), (
        "an any none of whose rules allows is the rule that denies"
    )
    assert evaluate(ROHIT, Request("assistive", "IN", later)) == Decision(True)
    just_after = datetime(2027, 4, 21, 19, 0, tzinfo=UTC)
    assert evaluate(ROHIT, Request("dubbing", "IN", just_after)) == Decision(False, "/all/2"), (
        "times compare as moments, whatever the offset"
    )
    end_of_term = datetime(2036, 4, 22, tzinfo=IST)
    assert evaluate(ROHIT, Request("assistive", "IN", end_of_term)) == Decision(False, "/all/2"), (
        "until excludes its own moment"
    )
    opening = datetime(2026, 4, 30, 18, 30, tzinfo=UTC)
    assert evaluate({"from": "2026-05-01T00:00:00+05:30"}, Request("ads", "IN", opening)) == Decision(True), (
        "from allows from its own moment on, whatever the offset"
    )

    nested = {"all": [{"all": [{"region": ["IN"]}, {"not": {"purpose": ["ads"]}}]}]}
    assert evaluate(nested, Request("ads", "IN", may)) == Decision(False, "/all/0/all/1"), (
        "the pointer leads through nested rules"
    )
    assert evaluate({"purpose": ["dubbing"]}, Request("ads", "IN", may)) == Decision(False, ""), (
        "the root rule's pointer is the empty string"
    )
    assert evaluate({"all": []}, Request("ads", "IN", may)) == Decision(True)
    assert evaluate({"any": []}, Request("ads", "IN", may)) == Decision(False, ""), (
        "an empty any allows nothing"
    )

    for broken in (
        {"any": [{"purpose": ["dubbing"]}, {"regoin": ["IN"]}]},
        {"purpose": ["dubbing"], "region": ["IN"]},
        {"all": [{"until": "2027-04-22T00:00:00"}]},
        {"not": [{"purpose": ["dubbing"]}]},
        {"purpose": "dubbing"},
    ):
        with pytest.raises(ValueError):
            evaluate(broken, Request("dubbing", "IN", may))
    with pytest.raises(ValueError):
        evaluate(ROHIT, Request("dubbing", "IN", datetime(2026, 5, 1, 10, 0)))
