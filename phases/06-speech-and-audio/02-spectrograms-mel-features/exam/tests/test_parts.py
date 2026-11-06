import copy
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import melkit.config
import pytest
from melkit.cache import FeatureCache, Features, clip_hash
from melkit.cmvn import OnlineCMVN, cmvn
from melkit.config import DEFAULTS, fingerprint, merge
from melkit.deltas import add_deltas, deltas
from melkit.features import (
    apply_filterbank,
    hz_to_mel,
    log_mel,
    log_mel_spectrogram,
    mel_filterbank,
    mel_to_hz,
    power_to_db,
    whisper_log_mel,
)
from melkit.service import FeatureService


def tone(freq: float, sr: int, seconds: float, amp: float = 0.5, seed: int = 0) -> list[float]:
    """A sine with a little noise, like the lesson's test signals."""
    rng = random.Random(seed)
    return [
        amp * math.sin(2.0 * math.pi * freq * i / sr) + rng.gauss(0.0, 0.01)
        for i in range(int(sr * seconds))
    ]


def close(a: list[list[float]], b: list[list[float]], tol: float = 1e-9) -> bool:
    """Two matrices have the same shape and agree value by value within tol."""
    return len(a) == len(b) and all(
        len(x) == len(y) and all(math.isclose(u, v, rel_tol=tol, abs_tol=tol) for u, v in zip(x, y))
        for x, y in zip(a, b)
    )


@pytest.mark.skip("Part 1")
def test_log_mel_frontend() -> None:
    """Log-mel features must match their docstrings at any sample rate, and stay fast."""
    sr = 8000
    clip = tone(1000.0, sr, 0.1)
    feats = log_mel_spectrogram(clip, sr, n_fft=256, hop=128, n_mels=40)
    assert [len(row) for row in feats] == [40] * 5, "one row of n_mels values per frame"
    assert [row.index(max(row)) for row in feats] == [18] * 5, "a 1 kHz tone peaks in mel band 18 of 40"
    assert hz_to_mel(1000.0) == pytest.approx(1000.0, abs=0.1), "HTK mel: 1000 Hz is about 1000 mel"
    assert mel_to_hz(hz_to_mel(3000.0)) == pytest.approx(3000.0, rel=1e-12), "mel_to_hz inverts hz_to_mel"
    wideband = log_mel_spectrogram(tone(1000.0, 16000, 0.1), 16000, n_fft=512, hop=256, n_mels=40, fmax=4000.0)
    assert [row.index(max(row)) for row in wideband] == [18] * 5, (
        "mel bands are in Hz: at 16 kHz, the same tone and fmax give the same band"
    )

    louder = log_mel_spectrogram([2.0 * s for s in clip], sr, n_fft=256, hop=128, n_mels=40)
    steps = [b - a for row_a, row_b in zip(feats, louder) for a, b in zip(row_a, row_b)]
    assert steps == pytest.approx([math.log(4.0)] * 200, rel=1e-6), (
        "log-mel is log power: twice the amplitude adds log(4)"
    )
    assert power_to_db([[100.0, 1.0, 0.5]])[0] == pytest.approx([20.0, 0.0, -3.0103], abs=1e-4), (
        "a 100x power ratio is 20 dB"
    )

    silence = log_mel_spectrogram([0.0] * 800, sr, n_fft=256, hop=128, n_mels=40)
    assert silence == [[math.log(1e-10)] * 40] * 5, "digital silence sits at log(floor)"
    assert log_mel([[0.0, 1e-12, 1e-9, 2.0]]) == [
        [math.log(1e-10), math.log(1e-10), math.log(1e-9), math.log(2.0)]
    ], "the floor replaces energies below it and leaves the rest exact"
    assert close(whisper_log_mel([[1e-6, 1e-12], [1.0, 1e-12]]), [[-0.5, -1.0], [1.0, -1.0]]), (
        "Whisper's floor sits 8 below the loudest value in the whole clip"
    )

    # 80 mels up to 8 kHz on 48 kHz audio, 2048-point frames: 1025 FFT bins per frame
    filters = mel_filterbank(80, 2048, 48000, fmax=8000.0)
    rng = random.Random(1)
    wide = [[rng.random() for _ in range(1025)] for _ in range(600)]
    rows = [f.dense(1025) for f in filters]
    by_hand = [[sum(w * p for w, p in zip(row, frame)) for row in rows] for frame in wide[:3]]
    assert close(apply_filterbank(wide[:3], filters), by_hand, tol=1e-12), (
        "each band is its filter's weighted sum of the power spectrum"
    )
    start = time.perf_counter()
    apply_filterbank(wide, filters)
    assert time.perf_counter() - start < 0.1, "the filterbank should be fast on wide spectra"


@pytest.mark.skip("Part 2")
def test_feature_cache(tmp_path) -> None:
    """Cached features come back exactly as stored, keyed by clip content and config."""
    clip = [0.0, 0.5, -0.25, 0.125]
    key = clip_hash(clip, 16000)
    assert isinstance(key, str) and key == clip_hash(list(clip), 16000), (
        "the same clip always hashes the same"
    )
    assert key != clip_hash(clip, 8000), "the sample rate is part of the clip"
    assert key != clip_hash([0.0, 0.5, -0.25, math.nextafter(0.125, 1.0)], 16000), (
        "every sample counts, at full precision"
    )

    tricky = Features(3, [[0.1 + 0.2, math.log(1e-10), 5e-324], [-1e300, 1 / 3, 1e-7]])
    root = str(tmp_path / "cache")
    cache = FeatureCache(root)
    assert cache.get(key, "cfg-a") is None, "a miss returns None"
    cache.put(key, "cfg-a", tricky)
    assert cache.get(key, "cfg-a") == tricky, "features must round-trip exactly"
    cache.put(key, "cfg-b", Features(40, []))
    assert cache.get(key, "cfg-a") == tricky, "each config keeps its own entry for the same clip"

    reopened = FeatureCache(root)
    assert reopened.get(key, "cfg-a") == tricky, "entries survive a reopen"
    assert reopened.get(key, "cfg-b").shape == (0, 40), "a clip too short for one frame keeps its width"
    assert reopened.get(clip_hash(clip, 8000), "cfg-a") is None
    for rows in ([[1.0, 2.0], [3.0, 4.0]], [[1.0, 2.0, 3.0], [4.0, 5.0], [6.0, 7.0, 8.0, 9.0]]):
        with pytest.raises(ValueError):
            reopened.put(key, "cfg-c", Features(3, rows))
    assert reopened.get(key, "cfg-c") is None, "a rejected matrix is not stored"


@pytest.mark.skip("Part 3")
def test_deltas_and_cmvn() -> None:
    """Deltas and per-utterance CMVN, on hand-checked numbers and on real log-mels."""
    ramp = [[float(t), 10.0 - 2.0 * t] for t in range(1, 7)]
    d = deltas(ramp, width=2)
    assert d[2] == pytest.approx([1.0, -2.0]) and d[3] == pytest.approx([1.0, -2.0]), (
        "away from the edges, the delta of a straight line is its slope"
    )
    assert [row[0] for row in d] == pytest.approx([0.5, 0.8, 1.0, 1.0, 0.8, 0.5]), (
        "frames past the edges repeat the first and last frame"
    )
    assert deltas([[3.0, 4.0]], width=2) == [[0.0, 0.0]], "a one-frame utterance has zero deltas"

    curve = [[float(t * t)] for t in range(12)]
    stacked = add_deltas(curve, windows=[2, 1])
    assert [len(row) for row in stacked] == [3] * 12, "each frame is static + delta + delta-delta"
    first = deltas(curve, 2)
    assert [row[1:] for row in stacked] == [a + b for a, b in zip(first, deltas(first, 1))], (
        "delta-delta is the delta of the deltas, each order with its own width"
    )
    assert [row[2] for row in stacked[3:9]] == pytest.approx([2.0] * 6), "t*t has delta-delta 2"
    assert add_deltas(curve, windows=[]) == curve, "no windows: static features only"

    s = math.sqrt(5.0)
    utterance = [[1.0, 5.0], [3.0, 5.0], [5.0, 5.0], [7.0, 5.0]]
    normed = cmvn(utterance)
    assert close(normed, [[-3 / s, 0.0], [-1 / s, 0.0], [1 / s, 0.0], [3 / s, 0.0]]), (
        "each dimension is normalized over time; a constant one becomes 0"
    )
    assert utterance == [[1.0, 5.0], [3.0, 5.0], [5.0, 5.0], [7.0, 5.0]], "cmvn leaves its input untouched"

    sr = 8000
    log_mels = log_mel_spectrogram(tone(700.0, sr, 0.25), sr, n_fft=256, hop=128, n_mels=40)
    feats = cmvn(add_deltas(log_mels))
    assert [len(row) for row in feats] == [120] * 14, "40 log-mels + deltas + delta-deltas per frame"
    for column in zip(*feats):
        mean = sum(column) / len(column)
        var = sum((v - mean) ** 2 for v in column) / len(column)
        assert abs(mean) < 1e-9 and math.isclose(var, 1.0, rel_tol=1e-9), (
            "after CMVN every dimension has mean 0 and variance 1"
        )


@pytest.mark.skip("Part 4")
def test_online_cmvn() -> None:
    """Live CMVN only uses frames that have arrived, and matches offline cmvn() as documented."""
    rng = random.Random(4)
    frames = [[rng.gauss(-8.0, 3.0), rng.gauss(2.0, 0.5), 1.5] for _ in range(40)]

    def run(sizes: list[int]) -> list[list[float]]:
        live = OnlineCMVN(dim=3, warmup=10)
        out, pos = [], 0
        for size in sizes:
            out += live.push(frames[pos : pos + size])
            pos += size
        return out + live.flush()

    runs = [run(sizes) for sizes in ([40], [1] * 40, [3, 0, 7, 1, 20, 9])]
    assert runs[0] == runs[1] == runs[2], "the same frames whatever the chunking"
    expected = [cmvn(frames[: max(t + 1, 10)])[t] for t in range(40)]
    assert close(runs[0], expected), (
        "frame t is normalized with the statistics of frames 0..max(t, warmup - 1)"
    )
    assert close(runs[0][-1:], cmvn(frames)[-1:]), (
        "the last frame sees the whole utterance, like offline cmvn"
    )

    live = OnlineCMVN(dim=3, warmup=10)
    assert live.push(frames[:9]) == [], "the first warmup frames are held back"
    assert len(live.push(frames[9:10])) == 10, "warm-up frames are released together"
    assert len(live.push(frames[10:13])) == 3, "after warm-up, frames come out as they arrive"
    assert live.flush() == []

    short = OnlineCMVN(dim=3, warmup=10)
    assert short.push(frames[:4]) == []
    assert close(short.flush(), cmvn(frames[:4])), (
        "a stream shorter than the warm-up is normalized at flush"
    )

    stream = [[rng.gauss(0.0, 1.0) for _ in range(13)] for _ in range(1000)]
    live = OnlineCMVN(dim=13, warmup=100)
    start = time.perf_counter()
    for frame in stream:
        live.push([frame])
    assert time.perf_counter() - start < 0.05, (
        "each new frame should cost the same, however long the stream"
    )


def reverse_keys(node):
    """The same config with every dict's keys in reverse order."""
    if isinstance(node, dict):
        return {key: reverse_keys(node[key]) for key in reversed(list(node))}
    return node


@pytest.mark.skip("Part 5")
def test_config_merge_and_fingerprint(tmp_path) -> None:
    """Layered configs merge as nested dicts, and their fingerprint keys the feature cache."""
    defaults = copy.deepcopy(DEFAULTS)
    model = {
        "sample_rate": 8000,
        "stft": {"n_fft": 256, "hop": 128},
        "mel": {"n_mels": 40, "fmax": 3800.0},
    }
    run = {"mel": {"n_mels": 24}, "deltas": {"windows": [3]}}
    cfg = merge(DEFAULTS, model, run)
    assert cfg["mel"] == {"n_mels": 24, "fmin": 0.0, "fmax": 3800.0}, (
        "nested dicts merge key by key; later layers win"
    )
    assert cfg["deltas"] == {"windows": [3]}, "a list is replaced whole, never merged"
    assert cfg["sample_rate"] == 8000 and cfg["log"] == defaults["log"]
    cfg["mel"]["n_mels"] = 1
    cfg["deltas"]["windows"].append(5)
    cfg["log"]["floor"] = 0.0
    assert DEFAULTS == defaults and run == {"mel": {"n_mels": 24}, "deltas": {"windows": [3]}}, (
        "merging leaves its inputs untouched"
    )
    with pytest.raises(KeyError, match=r"mel\.n_mel"):
        merge(DEFAULTS, {"mel": {"n_mel": 128}})
    with pytest.raises(KeyError, match="sample_rte"):
        merge(DEFAULTS, {"sample_rte": 8000})

    cfg = merge(DEFAULTS, model, run)
    fp = fingerprint(cfg)
    assert isinstance(fp, str) and fingerprint(reverse_keys(cfg)) == fp, (
        "key order, at any depth, does not change the fingerprint"
    )
    for change in ({"log": {"floor": 1e-12}}, {"mel": {"fmax": None}}, {"stft": {"hop": 129}}):
        assert fingerprint(merge(cfg, change)) != fp, f"any changed value changes the fingerprint: {change}"
    assert fingerprint(merge(cfg, {"deltas": {"windows": [2, 3]}})) != fingerprint(
        merge(cfg, {"deltas": {"windows": [3, 2]}})
    ), "list order matters"

    package_root = Path(melkit.config.__file__).resolve().parents[1]
    script = "import json, sys\nfrom melkit.config import fingerprint\nprint(fingerprint(json.loads(sys.argv[1])))"
    seen = set()
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(package_root)}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        done = subprocess.run(
            [sys.executable, "-c", script, json.dumps(cfg)],
            cwd=package_root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        seen.add(done.stdout.strip())
    assert seen == {fp}, "the fingerprint is the same in every process, so it can key an on-disk cache"

    cache = FeatureCache(str(tmp_path / "cache"))
    clip = tone(440.0, 8000, 0.1)
    first = FeatureService(cfg, cache)
    feats = first.features(clip, 8000)
    assert feats.shape == (5, 48) and first.computed == 1
    again = FeatureService(reverse_keys(cfg), cache)
    assert again.features(clip, 8000) == feats and again.computed == 0, (
        "the same config in another key order reuses the cached features"
    )
    wider = FeatureService(merge(cfg, {"mel": {"n_mels": 32}}), cache)
    assert wider.features(clip, 8000).shape == (5, 64) and wider.computed == 1, (
        "a changed config computes fresh features"
    )
