import asyncio
import itertools
import json
import math
import random
import time
import unicodedata

import pytest
from asrkit.ctc import VOCAB, greedy_decode, prefix_beam_search, transcribe
from asrkit.lattice import Arc, best_path, nbest
from asrkit.scoring import wer
from asrkit.service import ASRService
from asrkit.store import TranscriptStore, Utterance
from asrkit.stream import stream_words


def frame(probs: dict[str, float]) -> list[float]:
    """Log-probabilities of one frame ("_" is the blank); unlisted tokens share the rest."""
    rest = (1.0 - sum(probs.values())) / (len(VOCAB) - len(probs))
    return [math.log(probs.get(token, rest)) for token in VOCAB]


def frames_for(alignment: str) -> list[list[float]]:
    """One confident frame per character of a CTC alignment."""
    return [frame({char: 0.9}) for char in alignment]


def log_row(*probs: float) -> list[float]:
    return [math.log(p) if p > 0 else -math.inf for p in probs]


def collapse(path: tuple[int, ...]) -> tuple[int, ...]:
    """The lesson's two rules: merge repeats, then drop blanks (token 0)."""
    merged = [t for i, t in enumerate(path) if i == 0 or t != path[i - 1]]
    return tuple(t for t in merged if t != 0)


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def chunked(frames: list[list[float]], sizes: list[int]):
    pos = 0
    for size in sizes:
        yield frames[pos : pos + size]
        pos += size


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Split a Server-Sent Events stream into (event, data) pairs."""
    if not text:
        return []
    assert text.endswith("\n\n"), "every message ends with a blank line"
    events = []
    for message in text[:-2].split("\n\n"):
        kind, data = message.split("\n")
        assert kind.startswith("event: ") and data.startswith("data: "), (
            "each message is an event line, then a data line"
        )
        events.append((kind[len("event: ") :], json.loads(data[len("data: ") :])))
    return events


@pytest.mark.skip("Part 1")
def test_greedy_and_wer() -> None:
    """Greedy CTC decoding and WER follow the lesson, and scoring scales to long transcripts."""
    hello = transcribe(frames_for("_hh_e_ll_l_oo_ _ww_oo_rr_l_dd_"))
    assert wer("hello world", hello) == 0.0, "a clean decode scores zero"

    silence = transcribe(frames_for("_" * 40))
    assert wer("turn on the kitchen lights", silence) == 1.0, (
        "silence that decodes to nothing deletes every word"
    )
    assert wer("the cat sat on the mat", "the cat sat") == 0.5, (
        "WER counts errors per reference word"
    )
    assert wer("a b", "a b c d e") == 1.5, "insertions count in full, so WER can pass 1"

    ref = "please call stella and ask her to bring these things"
    hyp = "lease fall bella end mask fur two ring tease kings"  # a noisy line: every word misheard
    start = time.perf_counter()
    assert wer(ref, hyp) == 1.0
    assert time.perf_counter() - start < 0.03, "scoring should stay fast as utterances grow"

    meeting = [f"w{i}" for i in range(600)]
    heard = ["uh" if i % 10 == 9 else word for i, word in enumerate(meeting)]
    assert wer(" ".join(meeting), " ".join(heard)) == pytest.approx(0.1), (
        "score a full meeting transcript"
    )


@pytest.mark.skip("Part 2")
def test_transcript_store(tmp_path) -> None:
    """Transcripts come back from the store exactly, in NFC, including after a reopen."""
    path = str(tmp_path / "transcripts.sqlite3")

    def nfd(text: str) -> str:
        return unicodedata.normalize("NFD", text)

    zoe = "zo\u00eb-0001"  # composed, as typed into the annotation spreadsheet
    reference = "Zo\u00eb paid 25 m\u00b2 for the caf\u00e9 chairs, \ufb01nally."
    heard = "zoe paid twenty five meters for the cafe chairs finally"
    minutes = "회의록을 확인해 주세요"  # "please check the minutes", in Hangul syllables

    store = TranscriptStore(path)
    store.add_utterance(nfd(zoe), nfd(reference))  # the same id, from a macOS file name
    store.add_utterance("minutes-0002", nfd(minutes))
    store.add_hypothesis("minutes-0002", "w2v-v2", nfd(minutes))
    store.add_hypothesis(zoe, "w2v-v1", heard)
    store.add_hypothesis(nfd(zoe), "w2v-v2", reference)
    expected = Utterance(zoe, reference, {"w2v-v1": heard, "w2v-v2": reference})
    assert store.get(nfd(zoe)) == expected, "transcripts come back exactly, in NFC"
    assert store.get("minutes-0002") == Utterance("minutes-0002", minutes, {"w2v-v2": minutes}), (
        "Hangul is stored composed too"
    )
    with pytest.raises(KeyError):
        store.get("zoe-0001")
    with pytest.raises(ValueError):
        store.add_utterance(zoe, "a second reference")
    store.add_hypothesis(zoe, "w2v-v2", nfd(reference))  # the same transcript again
    with pytest.raises(ValueError):
        store.add_hypothesis(zoe, "w2v-v2", reference.lower())
    with pytest.raises(KeyError):
        store.add_hypothesis("no-such-utterance", "w2v-v1", "hello")
    store.close()

    reopened = TranscriptStore(path)
    assert reopened.pairs("w2v-v2") == [
        (zoe, reference, reference),
        ("minutes-0002", minutes, minutes),
    ], "a reopened store sees earlier transcripts, in the order the utterances were added"
    reopened.close()


@pytest.mark.skip("Part 3")
def test_prefix_beam_search() -> None:
    """Prefix beam search sums alignments in the log domain and keeps double letters."""
    soft = [log_row(0.6, 0.4)] * 2  # tokens: blank, a
    assert greedy_decode(soft) == []
    assert prefix_beam_search(soft, beam=4) == [
        ((1,), pytest.approx(math.log(0.64))),
        ((), pytest.approx(math.log(0.36))),
    ], "a prefix is as likely as all of its alignments together"
    assert prefix_beam_search(soft, beam=1) == [((), pytest.approx(math.log(0.36)))], (
        "only the beam best prefixes survive each frame"
    )
    a_or_ab = [log_row(0.1, 0.9, 0.0), log_row(0.35, 0.25, 0.4)]  # tokens: blank, a, b
    assert prefix_beam_search(a_or_ab, beam=1) == [((1,), pytest.approx(math.log(0.54)))], (
        "the beam keeps the prefixes with the most probability over all their alignments"
    )

    a_blank_a = [log_row(0.1, 0.9), log_row(0.9, 0.1), log_row(0.1, 0.9)]
    assert prefix_beam_search(a_blank_a)[0][0] == (1, 1), (
        "a blank between repeats keeps both letters"
    )

    rng = random.Random(7)
    weights = [[rng.random() + 0.05 for _ in range(3)] for _ in range(5)]
    small = [log_row(*(w / sum(row) for w in row)) for row in weights]
    exact: dict[tuple[int, ...], float] = {}
    for path in itertools.product(range(3), repeat=len(small)):
        p = math.exp(sum(small[t][token] for t, token in enumerate(path)))
        exact[collapse(path)] = exact.get(collapse(path), 0.0) + p
    found = dict(prefix_beam_search(small, beam=100))
    assert found.keys() == exact.keys() and all(
        math.isclose(found[prefix], math.log(p), rel_tol=1e-9) for prefix, p in exact.items()
    ), "with nothing pruned, every possible prefix gets its exact probability"

    masked = [log_row(0.5, 0.5, 0.0), log_row(0.5, 0.5, 0.0), log_row(0.3, 0.7, 0.0)]
    assert all(
        2 not in prefix and math.isfinite(score) for prefix, score in prefix_beam_search(masked)
    ), "a token the model rules out never appears"

    # 1800 frames is 36 s of audio at 20 ms per frame; tokens: blank, a, b, c, d
    long = [
        log_row(*(0.5 if k == target else 0.125 for k in range(5)))
        for target in [1, 2, 0, 3, 4, 0] * 300
    ]
    assert prefix_beam_search(long, beam=4)[0][0] == (1, 2, 3, 4) * 300, (
        "a long utterance must not underflow"
    )

    soft_o = frame({"_": 0.5, "o": 0.45})
    go_home = frames_for("_gg_") + [soft_o, soft_o] + frames_for("_ _hh_oo_mm_ee_")
    store = TranscriptStore()
    store.add_utterance("u1", "go home")
    service = ASRService(store)
    service.record("u1", "greedy", go_home)
    service.record("u1", "beam", go_home, beam=8)
    assert {m: [wer(r, h) for _, r, h in store.pairs(m)] for m in ("greedy", "beam")} == {
        "greedy": [0.5],
        "beam": [0.0],
    }, "beam search recovers the letter that greedy decoding drops"


@pytest.mark.skip("Part 4")
def test_stream_words() -> None:
    """A live stream becomes partial and final word events, whatever the chunking."""
    speech = frames_for(" hh_e_ll_l_oo_ _ _w_oo_rr_l_dd")  # 20 ms per frame
    # "hello" has its letters in frames 1-12 and "world" in frames 18-29
    expected = [("partial", {"text": text}) for text in ("h", "he", "hel", "hell", "hello")]
    expected.append(("final", {"text": "hello", "start_ms": 20, "end_ms": 260}))
    expected += [("partial", {"text": text}) for text in ("w", "wo", "wor", "worl", "world")]
    expected.append(("final", {"text": "world", "start_ms": 360, "end_ms": 600}))
    for sizes in ([30], [1] * 30, [2, 0, 5, 1, 7, 3, 12]):
        text = "".join(collect(stream_words(chunked(speech, sizes))))
        assert parse_sse(text) == expected, f"same events whatever the chunking, e.g. {sizes[:7]}"
    go_on = parse_sse("".join(collect(stream_words(chunked(frames_for("go on"), [5])))))
    assert [data["text"] for kind, data in go_on if kind == "final"] == ["go", "on"], (
        "a word can start with the letter the previous word ended with"
    )

    pulled: list[int] = []

    async def live():
        for i in range(100):
            pulled.append(i)
            yield [frame({"h": 0.9})]

    async def first_event() -> str:
        agen = stream_words(live())
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert parse_sse(asyncio.run(first_event())) == [("partial", {"text": "h"})]
    assert len(pulled) <= 2, "emit each event as soon as it is known"


LATTICE = [
    Arc(0, 5, "it's", -2.0, -1.0),
    Arc(0, 13, None, -1.0),  # a pause before the first word
    Arc(13, 5, "it's", -2.0, -1.0),
    Arc(5, 3, "hard", -2.5, -1.5),
    Arc(3, 9, "to", -1.0, -0.5),
    Arc(3, 11, "two", -1.5, -3.0),  # 11 is a dead end
    Arc(9, 1, "recognize", -9.0, -4.0),
    Arc(1, 6, "peach", -5.5, -3.0),
    Arc(1, 6, "speech", -5.0, -1.0),
    Arc(9, 2, "wreck", -4.0, -8.0),
    Arc(2, 4, "a", -1.0, -2.0),
    Arc(4, 8, "nice", -2.0, -3.0),
    Arc(8, 6, "beach", -3.5, -4.0),
    Arc(6, 7, None, -0.5),  # trailing silence, two ways
    Arc(6, 10, None, -0.25),
    Arc(10, 7, None, -0.5),
]


@pytest.mark.skip("Part 5")
def test_lattice_nbest() -> None:
    """The best transcripts come out of a word lattice without enumerating its paths."""
    assert best_path(LATTICE, 0, 7) == ("it's hard to recognize speech", -28.0), (
        "follow the arcs, whatever the node numbers"
    )
    assert nbest(LATTICE, 0, 7, n=4) == [
        ("it's hard to recognize speech", -28.0),
        ("it's hard to recognize peach", -30.5),
        ("it's hard to wreck a nice beach", -36.5),
    ], "n-best lists each transcript once, alternatives between the same two nodes included"
    assert best_path(LATTICE, 0, 7, lm_weight=0.0) == ("it's hard to wreck a nice beach", -16.5), (
        "lm_weight scales the language-model scores only"
    )
    with pytest.raises(ValueError):
        best_path(LATTICE, 7, 0)

    ladder = [
        Arc(i, i + 1, word, -1.0, lm)
        for i in range(20)
        for word, lm in ((f"a{i}", -0.5), (f"b{i}", -0.5 - (i + 1) / 8))
    ]
    start = time.perf_counter()
    top = nbest(ladder, 0, 20, n=2)
    elapsed = time.perf_counter() - start
    assert top == [
        (" ".join(f"a{i}" for i in range(20)), -30.0),
        (" ".join(["b0"] + [f"a{i}" for i in range(1, 20)]), -30.125),
    ], "the runner-up differs where that costs least"
    assert elapsed < 0.05, "the work should grow with the arcs, not with the 2**20 paths"

    with pytest.raises(ValueError):
        nbest(LATTICE + [Arc(11, 12, "um", -1.0), Arc(12, 11, "uh", -1.0)], 0, 7, n=1)
