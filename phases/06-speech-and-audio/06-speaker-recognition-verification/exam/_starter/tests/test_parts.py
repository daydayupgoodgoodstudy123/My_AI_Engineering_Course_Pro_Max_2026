import asyncio
import math
import random
import re
import time

import pytest
from speakerid.cluster import agglomerate, cut
from speakerid.diarize import Segment, diarize_stream
from speakerid.registry import SpeakerRegistry
from speakerid.scoring import Verifier, threshold_at_far
from speakerid.trials import eer, parse_trials, score_trials


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def arrive(segments: list[Segment]):
    for segment in segments:
        yield segment


TRIALS = """\
1 alice/1.wav alice/2.wav
1 alice/1.wav alice/3.wav
1 bob/1.wav bob/2.wav
1 alice/1.wav alice/4.wav
0 alice/1.wav bob/1.wav
0 alice/3.wav bob/1.wav
0 alice/2.wav bob/2.wav
0 bob/2.wav alice/1.wav
"""

EMBEDDINGS = {
    "alice/1.wav": [5.0, 0.0],
    "alice/2.wav": [12.0, 5.0],
    "alice/3.wav": [4.0, 3.0],
    "alice/4.wav": [0.0, 0.0],  # a silent recording: the embedder returns the zero vector
    "bob/1.wav": [3.0, 4.0],
    "bob/2.wav": [5.0, 12.0],
}


@pytest.mark.skip("Part 1")
def test_trial_list_eer() -> None:
    """EER over a VoxCeleb-style trial list must be correct, fast, and blind to embedding norms."""
    assert eer([0.9, 0.8, 0.6], [0.7, 0.5, 0.4, 0.3]) == pytest.approx((7 / 24, 0.7)), (
        "the EER threshold is where false accepts and false rejects come closest"
    )
    assert eer([0.6, 0.6, 0.8, 0.8], [0.2, 0.6, 0.6, 0.7]) == pytest.approx((0.375, 0.7)), (
        "a score equal to the threshold is accepted"
    )
    assert eer([0.5] * 3, [0.5] * 5) == pytest.approx((0.5, 0.5)), (
        "a scorer that cannot tell trials apart has an EER of 0.5"
    )

    target, nontarget = score_trials(parse_trials(TRIALS), EMBEDDINGS)
    assert eer(target, nontarget) == pytest.approx((0.25, 0.8)), (
        "EER of the trial list, scored by cosine"
    )

    rng = random.Random(0)
    target = [rng.gauss(0.6, 0.15) for _ in range(6000)]
    nontarget = [rng.gauss(0.2, 0.15) for _ in range(6000)]
    start = time.perf_counter()
    eer(target, nontarget)
    assert time.perf_counter() - start < 0.1, "eer should be fast on a large trial list"


@pytest.mark.skip("Part 2")
def test_enrollment_registry(tmp_path) -> None:
    """Enrollments persist, and a template depends only on the enrollments a speaker holds."""
    small = SpeakerRegistry()
    for vec in ([2.0, 0.0], [0.0, 5.0], [0.0, 0.5]):
        small.enroll("carol", vec)
    assert small.template("carol") == pytest.approx([1 / math.sqrt(5), 2 / math.sqrt(5)]), (
        "a template is the mean of the unit-length enrollments, scaled to unit length"
    )
    with pytest.raises(ValueError):
        small.enroll("carol", [0.0, 0.0])
    with pytest.raises(ValueError):
        small.enroll("dave", [1.0, 2.0, 3.0])
    with pytest.raises(KeyError):
        small.template("dave")
    small.close()

    path = str(tmp_path / "speakers.sqlite3")
    rng = random.Random(18)
    alice = [[rng.gauss(0.0, 1.0) * scale for _ in range(16)] for scale in (0.5, 1.0, 2.0, 4.0)]
    bob = [[rng.gauss(0.0, 1.0) for _ in range(16)] for _ in range(2)]
    registry = SpeakerRegistry(path)
    bob_ids = [registry.enroll("bob", vec) for vec in bob]
    alice_ids = [registry.enroll("alice", vec) for vec in alice]
    assert len(set(alice_ids + bob_ids)) == 6, "enroll returns a new id every time"
    assert registry.speakers() == ["alice", "bob"], "speakers are listed by name"
    clean = registry.template("alice")
    noisy = registry.enroll("alice", [rng.gauss(0.0, 1.0) for _ in range(16)])
    assert registry.template("alice") != clean, "a new enrollment moves the template"
    registry.remove(noisy)
    assert registry.template("alice") == clean, (
        "removing an enrollment gives back the earlier template exactly"
    )
    with pytest.raises(KeyError):
        registry.remove(noisy)
    for enrollment_id in bob_ids:
        registry.remove(enrollment_id)
    assert registry.speakers() == ["alice"], "a speaker with no enrollments is no longer enrolled"
    registry.close()

    reopened = SpeakerRegistry(path)
    stored = [(e.enrollment_id, e.embedding) for e in reopened.enrollments("alice")]
    assert stored == list(zip(alice_ids, alice)), (
        "enrollments round-trip exactly, in the order they were added"
    )
    assert reopened.template("alice") == clean, "a reopened registry rebuilds the same template"
    with pytest.raises(KeyError):
        reopened.template("bob")
    reopened.close()


def cohort_member(with_template: float, with_clip: float) -> list[float]:
    """A unit embedding whose cosines with [1, 0, 0] and [0.6, 0.8, 0] are the given values."""
    y = (with_clip - 0.6 * with_template) / 0.8
    return [with_template, y, math.sqrt(1.0 - with_template**2 - y**2)]


# Cosines with alice's template: 0.36, 0.12, 0.04, -0.20 (mean 0.08, std 0.2; top two 0.24 +- 0.12).
# Cosines with alice's clip: 0.05, -0.25, 0.45, 0.15 (mean 0.1, std 0.25; top two 0.3 +- 0.15).
COHORT = [
    cohort_member(0.36, 0.05),
    cohort_member(0.12, -0.25),
    cohort_member(0.04, 0.45),
    cohort_member(-0.20, 0.15),
]


@pytest.mark.skip("Part 3")
def test_snorm_verification() -> None:
    """Claims are S-normalized against an imposter cohort and accepted at a target FAR."""
    assert threshold_at_far([0.5, 0.95], [0.1, 0.2, 0.3, 0.9], 0.25) == 0.5, (
        "the lowest dev score whose FAR meets the target"
    )
    assert threshold_at_far([0.6, 0.8], [0.2, 0.6, 0.6, 0.7], 0.5) == 0.7, (
        "a non-target scoring exactly the threshold is a false accept"
    )
    with pytest.raises(ValueError):
        threshold_at_far([0.5], [0.9], 0.0)

    registry = SpeakerRegistry()
    registry.enroll("alice", [2.0, 0.0, 0.0])
    alice_clip = [3.0, 4.0, 0.0]  # raw cosine 0.6 with alice's template
    lookalike = [1.0, 0.0, 1.0]  # raw cosine 0.71, but close to the whole cohort too
    stranger = [0.0, -1.0, 0.5]  # raw cosine 0.0
    s_norm = Verifier(registry, COHORT)
    assert s_norm.score("alice", alice_clip) == pytest.approx(0.5 * (2.6 + 2.0)), (
        "S-norm averages the template-side and clip-side normalized scores"
    )
    as_norm = Verifier(registry, COHORT, top_k=2)
    assert as_norm.score("alice", alice_clip) == pytest.approx(0.5 * (3.0 + 2.0)), (
        "AS-norm: each side keeps its own top_k cohort scores"
    )

    verifier = Verifier(registry, COHORT)
    with pytest.raises(RuntimeError):
        verifier.verify("alice", alice_clip)
    dev = [("alice", alice_clip, True), ("alice", lookalike, False), ("alice", stranger, False)]
    assert verifier.calibrate(dev, target_far=0.0) == pytest.approx(2.3), (
        "calibrate on the same S-normalized scores that verify compares"
    )
    assert verifier.verify("alice", alice_clip), "a claim scoring exactly the threshold is accepted"
    assert not verifier.verify("alice", lookalike), "the lookalike is rejected at 0% dev FAR"
    assert not verifier.verify("alice", stranger)


def at(degrees: float, norm: float = 1.0) -> list[float]:
    """A 2-d embedding pointing `degrees` around the circle."""
    rad = math.radians(degrees)
    return [norm * math.cos(rad), norm * math.sin(rad)]


MEETING = [
    Segment(0.0, 1.5, at(0, norm=10.0)),
    Segment(1.5, 3.0, at(30)),
    Segment(3.0, 4.5, at(60)),
    Segment(4.5, 6.0, at(85)),
    Segment(6.25, 7.0, at(75)),
    Segment(7.0, 8.5, at(-17)),
    Segment(8.5, 9.0, at(200)),
    Segment(9.5, 11.0, at(190)),
]


@pytest.mark.skip("Part 4")
def test_online_diarization() -> None:
    """Speaker turns stream out as RTTM lines while the segments arrive."""
    threshold = math.cos(math.radians(50))
    text = "".join(collect(diarize_stream(arrive(MEETING), threshold)))
    rows = [line.split() for line in text.splitlines()]
    assert rows and all(
        len(row) == 10 and row[:3] == ["SPEAKER", "meeting", "1"] and row[5:7] == ["<NA>", "<NA>"]
        for row in rows
    ), "one RTTM SPEAKER line per turn"
    assert all(re.fullmatch(r"\d+\.\d{3}", field) for row in rows for field in row[3:5]), (
        "RTTM times are in seconds with three decimals"
    )
    turns = [(float(row[3]), float(row[4]), row[7]) for row in rows]
    assert all(a[0] + a[1] <= b[0] for a, b in zip(turns, turns[1:])), (
        "turns follow one another: the fifth RTTM field is the turn's duration"
    )
    assert turns == [
        (0.0, 4.5, "spk0"),
        (4.5, 2.5, "spk1"),
        (7.0, 1.5, "spk0"),
        (8.5, 2.5, "spk2"),
    ], (
        "each segment joins the most similar speaker centroid;"
        " a speaker's consecutive segments are one turn"
    )

    pulled: list[int] = []

    async def probe():
        for index, segment in enumerate(MEETING):
            pulled.append(index)
            yield segment

    async def first_turn() -> str:
        agen = diarize_stream(probe(), threshold)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert asyncio.run(first_turn()).split()[7] == "spk0"
    assert len(pulled) <= 4, "a turn is written as soon as the next speaker starts"
    assert collect(diarize_stream(arrive([]), threshold)) == [], "an empty meeting has no turns"


@pytest.mark.skip("Part 5")
def test_dendrogram_cut() -> None:
    """Flat speaker clusters from an agglomerative-clustering tree of any depth."""
    tree = (((0, 3, 0.9), 1, 0.7), ((2, 5, 0.95), 4, 0.4), 0.2)
    assert cut(tree, 0.5) == [[0, 1, 3], [2, 5], [4]], (
        "a subtree whose merges all reach the threshold is one cluster"
    )
    assert cut(tree, 0.7) == [[0, 1, 3], [2, 5], [4]], "a merge exactly at the threshold joins"
    assert cut(tree, 0.92) == [[0], [1], [2, 5], [3], [4]], (
        "clusters are ordered by their first index"
    )
    assert cut(tree, 0.1) == [[0, 1, 2, 3, 4, 5]]
    for threshold in (0.3, 0.95):  # segment 1 appears twice: in one cluster, then in two
        with pytest.raises(ValueError):
            cut(((0, 1, 0.9), 1, 0.5), threshold)

    # Segment 2 sits above the middle of segments 0 and 1. It is less similar to either of them
    # than they are to each other, yet centroid linkage joins it to the pair at a higher similarity.
    inverted = agglomerate([[1.0, 0.0, 0.0], [1.0, 1.732, 0.0], [1.732, 1.0, 3.0]])
    assert cut(inverted, 0.52) == [[0], [1], [2]], (
        "every merge inside a cluster reaches the threshold, not only the last one"
    )

    rng = random.Random(5)
    voices = {"A": [1.0, 0.0, 0.0, 0.0], "B": [0.0, 1.0, 0.0, 0.0], "C": [0.0, 0.0, 1.0, 0.0]}
    segments = [[x + rng.gauss(0.0, 0.15) for x in voices[who]] for who in "ABACBCACB"]
    assert cut(agglomerate(segments), 0.5) == [[0, 2, 6], [1, 4, 8], [3, 5, 7]], (
        "agglomerate then cut recovers the three speakers"
    )

    chain = 0
    for index in range(1, 3000):
        chain = (chain, index, 0.9)
    clusters = cut(chain, 0.5)
    assert len(clusters) == 1 and clusters[0] == list(range(3000)), (
        "trees can be thousands of merges deep"
    )
