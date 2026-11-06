import asyncio
import csv
import io
import random
import time

import pytest
from evalsuite.board import Entry, Leaderboard
from evalsuite.bootstrap import paired_bootstrap, percentile_interval
from evalsuite.scoring import NORMALIZER, score
from evalsuite.service import EvalService
from evalsuite.stream import Scored, stream_report
from evalsuite.suite import suite_scores


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def batched(items: list, sizes: list[int]):
    pos = 0
    for size in sizes:
        yield items[pos : pos + size]
        pos += size


@pytest.mark.skip("Part 1")
def test_normalized_scoring() -> None:
    """Formatting is not a recognition error, in any script; a misrecognition still is."""
    assert score("我们明天去公园", "我们今天去公园", "zh") == pytest.approx(1 / 7), (
        "Chinese is scored per character"
    )
    assert score("会議は３時からです。", "会議は3時からです", "ja") == 0.0, (
        "full-width forms and punctuation are formatting, not errors"
    )
    assert score("3号楼", "5号楼", "zh") == pytest.approx(1 / 3), "a wrong digit is a real error"
    assert score("Привет, мир!", "привет мир", "ru") == 0.0, "words in every script are kept"
    assert score("मुझे दो किताबें चाहिए", "मुझे दो किताब चाहिए", "hi") == pytest.approx(1 / 4), (
        "a vowel sign is part of the word"
    )

    assert score("What's the weather today?", "what is the weather today", "en") == 0.0, (
        "a contraction and its expansion are the same words"
    )
    assert score("Set a 25-minute timer.", "set a twenty five minute timer", "en") == 0.0, (
        "numbers are compared as spoken words"
    )
    assert score("She said 'yes'.", "she said yes", "en") == 0.0, "quotation marks are punctuation"
    assert score("Turn ON the kitchen lights!", "turn off the kitchen lights", "en") == (
        pytest.approx(0.2)
    ), "a misrecognized word still counts"
    typed = "un cafe\u0301 cre\u0300me s'il vous plai\u0302t"  # decomposed accents
    assert score("Un café crème, s\u2019il vous plaît.", typed, "fr") == 0.0, (
        "the same letters, however they were typed"
    )
    assert score("un café noir", "un cafe noir", "fr") == pytest.approx(1 / 3), (
        "an accent is part of the word"
    )

    test_set = [
        ("我们明天去公园。", "我们今天去公园", "zh"),
        ("What's the weather in Paris today?", "what is the weather in paris today", "en"),
        ("Set a 25-minute timer.", "set a twenty five minute time", "en"),
        ("Un café noir, s\u2019il vous plaît.", "un cafe noir s'il vous plait", "fr"),
    ] * 6
    start = time.perf_counter()
    for reference, hypothesis, language in test_set:
        score(reference, hypothesis, language)
    assert time.perf_counter() - start < 0.1, "scoring should keep up with a full test set"


@pytest.mark.skip("Part 2")
def test_leaderboard(tmp_path) -> None:
    """Results come back exactly after a reopen; a re-run replaces a result but not its place."""
    path = str(tmp_path / "board.sqlite3")
    # one error apart on the 52,343 words of LibriSpeech test-other: both print as 6.05 %
    tdt, aed = 3167 / 52343, 3166 / 52343
    board = Leaderboard(path)
    board.submit("tdt-0.6b", "librispeech-other", "wer", tdt, 2939, (0.0574, 0.0637), NORMALIZER)
    assert board.get("tdt-0.6b", "librispeech-other", "wer") == Entry(
        "tdt-0.6b", "librispeech-other", "wer", tdt, 2939, (0.0574, 0.0637), NORMALIZER
    ), "a result comes back exactly as submitted"
    board.submit("ctc-1.1b", "librispeech-other", "wer", tdt, 2939, (0.0573, 0.0638), NORMALIZER)
    board.submit(
        "aed-1.5b", "librispeech-other", "wer", 0.0575, 2939, (0.0544, 0.0607), "whisper-en"
    )
    with pytest.raises(ValueError):
        board.ranking("librispeech-other", "wer")
    board.submit("aed-1.5b", "librispeech-other", "wer", aed, 2939, (0.0573, 0.0636), NORMALIZER)
    board.submit("tdt-0.6b", "librispeech-other", "wer", tdt, 2939, (0.0575, 0.0636), NORMALIZER)
    assert board.get("tdt-0.6b", "librispeech-other", "wer").ci == (0.0575, 0.0636), (
        "a re-run replaces the result"
    )
    board.submit("f5-tts", "seed-tts-en", "utmos", 3.95, 1088, (3.91, 3.99), "utmos-v2")
    board.submit("ground-truth", "seed-tts-en", "utmos", 4.08, 1088, (4.05, 4.11), "utmos-v2")
    board.close()

    reopened = Leaderboard(path)
    assert reopened.get("aed-1.5b", "librispeech-other", "wer") == Entry(
        "aed-1.5b", "librispeech-other", "wer", aed, 2939, (0.0573, 0.0636), NORMALIZER
    ), "a reopened board has every result, as last submitted"
    assert [e.model for e in reopened.ranking("librispeech-other", "wer")] == [
        "aed-1.5b",
        "tdt-0.6b",
        "ctc-1.1b",
    ], "lowest WER first, by exact value; a tie keeps the order the models first appeared"
    utmos = [e.model for e in reopened.ranking("seed-tts-en", "utmos")]
    assert utmos == ["ground-truth", "f5-tts"], "a higher UTMOS ranks first"
    with pytest.raises(KeyError):
        reopened.get("aed-1.5b", "librispeech-clean", "wer")
    with pytest.raises(ValueError):
        reopened.submit("x", "librispeech-other", "bleu", 0.3, 100, (0.2, 0.4), NORMALIZER)
    with pytest.raises(ValueError):
        reopened.submit("x", "seed-tts-en", "utmos", 5.2, 100, (5.0, 5.4), "utmos-v2")
    with pytest.raises(ValueError):
        reopened.submit("x", "librispeech-other", "wer", 0.06, 100, (0.07, 0.08), NORMALIZER)
    reopened.submit("tiny-asr", "short-commands", "wer", 1.25, 40, (1.05, 1.5), NORMALIZER)
    assert reopened.get("tiny-asr", "short-commands", "wer").value == 1.25, (
        "insertions can push WER past 1"
    )
    reopened.close()


COMMANDS = {
    "c1": "What's the weather today?",
    "c2": "Set a 25-minute timer.",
    "c3": "Turn on the kitchen lights.",
    "c4": "Play some jazz, please.",
    "c5": "Call Zoë at 6.",
    "c6": "Remind me to buy oat milk.",
}
OLD_RUN = {  # c4 failed to decode
    "c1": "what is the weather today",
    "c2": "set a twenty five minute time",
    "c3": "turn off the kitchen light",
    "c5": "call zoe at six",
    "c6": "remind me to buy milk",
}
NEW_RUN = {
    "c1": "What\u2019s the weather today",
    "c2": "set a 25 minute timer",
    "c3": "turn on the kitchen light",
    "c4": "play some jazz please",
    "c5": "Call Zoë at six.",
    "c6": "remind me to buy oat milk",
}


@pytest.mark.skip("Part 3")
def test_paired_bootstrap() -> None:
    """Two systems are compared on the same utterances, with a seeded paired bootstrap."""
    replicates = [i / 1000 for i in range(1000)]
    assert percentile_interval(replicates) == (0.025, 0.974), (
        "drop the same number of replicates at each end"
    )
    assert percentile_interval(replicates, 0.9) == (0.05, 0.949), (
        "a 90% interval drops 50 at each end"
    )
    assert percentile_interval(replicates[::-1]) == (0.025, 0.974), "replicates come in any order"

    rng = random.Random(5)
    units = {f"utt{i:02d}": rng.randint(5, 30) for i in range(40)}
    baseline = {u: (rng.randint(1, n // 2), n) for u, n in units.items()}
    better = {u: (e - 1 if i % 4 else e, n) for i, (u, (e, n)) in enumerate(baseline.items())}
    result = paired_bootstrap(baseline, dict(reversed(better.items())), replicates=1000, seed=7)
    assert result.delta == pytest.approx(-30 / sum(units.values())), (
        "delta is the candidate's corpus error rate minus the baseline's"
    )
    assert result.ci[1] < 0 and result.p_better == 1.0, (
        "paired utterance by utterance, one error fewer on most of them is a clear win"
    )
    assert paired_bootstrap(dict(reversed(baseline.items())), better, 1000, seed=7) == result, (
        "the same seed gives the same answer, whatever order the runs list utterances in"
    )
    assert paired_bootstrap(baseline, better, 1000, seed=8).ci != result.ci, (
        "the seed decides the draws"
    )
    state = random.getstate()
    paired_bootstrap(baseline, better, 50, seed=1)
    assert random.getstate() == state, "the bootstrap leaves the global random state alone"

    one_fix = {**baseline, "utt07": (baseline["utt07"][0] - 1, units["utt07"])}
    close = paired_bootstrap(baseline, one_fix, 1000, seed=7)
    assert close.ci[0] < 0 and close.ci[1] == 0.0, "one fixed utterance is not a significant win"
    assert 0.5 < close.p_better < 0.75, (
        "a replicate that leaves that utterance out is a tie, not a win"
    )
    with pytest.raises(ValueError):
        paired_bootstrap(baseline, {u: better[u] for u in list(better)[:-1]})
    with pytest.raises(ValueError):
        paired_bootstrap(baseline, {**better, "utt40": (2, 12)})
    renamed = {("utt40" if u == "utt39" else u): v for u, v in better.items()}
    with pytest.raises(ValueError):
        paired_bootstrap(baseline, renamed)
    with pytest.raises(ValueError):
        paired_bootstrap(baseline, {**better, "utt00": (1, units["utt00"] + 1)})

    service = EvalService(Leaderboard(), replicates=500, seed=0)
    comparison = service.compare(COMMANDS, OLD_RUN, NEW_RUN, "en")
    assert comparison.delta == pytest.approx(-8 / 30), (
        "formatting is not an error; a failed decode is"
    )
    assert comparison.ci[1] < 0, "the new run is better on this test set"
    entry = service.publish("new-asr", "assistant-commands", COMMANDS, NEW_RUN, "en")
    assert (entry.metric, entry.value, entry.n, entry.protocol) == (
        "wer",
        pytest.approx(1 / 30),
        6,
        NORMALIZER,
    ), "publish puts the run's WER on the board"
    assert entry.ci[0] <= entry.value <= entry.ci[1], "the interval brackets the published rate"


SCORED = [
    Scored("u1", "read", 1, 10),
    Scored("u2", "accented, L2", 6, 8),
    Scored("u3", "read", 0, 20),
    Scored("u4", "accented, L2", 2, 4),
    Scored("u5", "kids", 3, 6),
]


def report(sizes: list[int], every: int) -> str:
    return "".join(collect(stream_report(batched(SCORED, sizes), every)))


def parse(text: str) -> list[tuple[int, str, int, float]]:
    return [
        (int(row["seen"]), row["domain"], int(row["utterances"]), float(row["rate"]))
        for row in csv.DictReader(io.StringIO(text))
    ]


@pytest.mark.skip("Part 4")
def test_stream_report() -> None:
    """Running error rates pool counts per domain while results arrive, whatever the batching."""
    text = report([5], every=2)
    assert parse(text) == [
        (2, "accented, L2", 1, pytest.approx(6 / 8)),
        (2, "read", 1, pytest.approx(1 / 10)),
        (2, "*", 2, pytest.approx(7 / 18)),
        (4, "accented, L2", 2, pytest.approx(8 / 12)),
        (4, "read", 2, pytest.approx(1 / 30)),
        (4, "*", 4, pytest.approx(9 / 42)),
        (5, "accented, L2", 2, pytest.approx(8 / 12)),
        (5, "kids", 1, pytest.approx(3 / 6)),
        (5, "read", 2, pytest.approx(1 / 30)),
        (5, "*", 5, pytest.approx(12 / 48)),
    ], "a rate pools its domain's errors over its units; * pools every utterance"
    for sizes in ([1] * 5, [3, 0, 2]):
        assert report(sizes, every=2) == text, (
            f"the same report whatever the batching, e.g. {sizes}"
        )
    assert [row[0] for row in parse(report([5], every=5))] == [5, 5, 5, 5], (
        "a report that already covers every utterance is not repeated"
    )
    empty = csv.DictReader(io.StringIO("".join(collect(stream_report(batched([], []), 2)))))
    assert empty.fieldnames == ["seen", "domain", "utterances", "rate"] and list(empty) == [], (
        "an empty run still writes the header"
    )

    pulled: list[int] = []

    async def live():
        for i in range(100):
            pulled.append(i)
            yield [Scored(f"live{i}-{j}", "read", 1, 10) for j in range(10)]

    async def first_report() -> list[str]:
        agen = stream_report(live(), every=20)
        lines: list[str] = []
        async for chunk in agen:
            lines += chunk.splitlines()
            if len(lines) > 1:
                break
        await agen.aclose()
        return lines

    assert asyncio.run(first_report())[1] == "20,read,20,0.1", (
        "the first report comes after 20 utterances"
    )
    assert len(pulled) <= 3, "write each report as soon as it is due"


SUITE = {
    "name": "audio-2026",
    "children": [
        {
            "name": "asr",
            "weight": 2,
            "children": [
                {"name": "librispeech-other", "children": [{"metric": "wer"}]},
                {"name": "fleurs-zh", "children": [{"metric": "cer"}]},
            ],
        },
        {
            "name": "tts",
            "children": [
                {
                    "name": "seed-tts-en",
                    "children": [{"metric": "utmos", "weight": 3}, {"metric": "wer"}],
                },
            ],
        },
        {
            "name": "understanding",
            "children": [
                {"name": "mmau-pro-speech", "children": [{"metric": "accuracy"}]},
                {"name": "mmau-pro-sound", "children": [{"metric": "accuracy"}]},
                {"name": "mmau-pro-multi-audio", "weight": 0, "children": [{"metric": "accuracy"}]},
            ],
        },
    ],
}
RESULTS = {
    ("librispeech-other", "wer"): 0.08,
    ("fleurs-zh", "cer"): 1.25,  # a broken run that inserts more characters than it hears
    ("seed-tts-en", "utmos"): 3.8,
    ("seed-tts-en", "wer"): 0.02,
    ("mmau-pro-speech", "accuracy"): 0.6,
    ("mmau-pro-sound", "accuracy"): 0.5,
    ("mmau-pro-multi-audio", "accuracy"): 0.22,
}


@pytest.mark.skip("Part 5")
def test_suite_scores() -> None:
    """Every node of a nested suite gets a weighted 0..1 score; a missing result is never hidden."""
    scores = suite_scores(SUITE, RESULTS)
    assert scores["audio-2026/asr/librispeech-other/wer"] == pytest.approx(0.92), (
        "a lower error rate scores higher"
    )
    assert scores["audio-2026/asr/fleurs-zh/cer"] == 0.0, "scores stay between 0 and 1"
    assert scores["audio-2026/tts/seed-tts-en"] == pytest.approx((3 * 0.7 + 0.98) / 4), (
        "a subset weighs its metrics"
    )
    assert scores["audio-2026/understanding"] == pytest.approx(0.55), (
        "a weight-0 subset does not count"
    )
    multi_audio = scores["audio-2026/understanding/mmau-pro-multi-audio/accuracy"]
    assert multi_audio == pytest.approx(0.22), "a weight-0 subset is still reported"
    assert scores["audio-2026"] == pytest.approx((2 * 0.46 + 0.77 + 0.55) / 4), (
        "a group weighs its children"
    )
    assert len(scores) == 17, "every node is reported, by its path"

    without_sound = {k: v for k, v in RESULTS.items() if k != ("mmau-pro-sound", "accuracy")}
    partial = suite_scores(SUITE, without_sound)
    assert partial["audio-2026/understanding/mmau-pro-sound"] is None, (
        "a missing result has no score"
    )
    assert partial["audio-2026/understanding"] is None and partial["audio-2026"] is None, (
        "a missing result is never averaged away"
    )
    assert partial["audio-2026/asr"] == scores["audio-2026/asr"], (
        "complete branches keep their scores"
    )
    without_multi = {k: v for k, v in RESULTS.items() if k != ("mmau-pro-multi-audio", "accuracy")}
    root = suite_scores(SUITE, without_multi)["audio-2026"]
    assert root == pytest.approx(scores["audio-2026"]), "a missing weight-0 result blocks nothing"
    unknown = {"name": "s", "children": [{"name": "b", "children": [{"metric": "bleu"}]}]}
    with pytest.raises(ValueError):
        suite_scores(unknown, {})
    negative = {
        "name": "s",
        "children": [{"name": "b", "weight": -1, "children": [{"metric": "wer"}]}],
    }
    with pytest.raises(ValueError):
        suite_scores(negative, {})
