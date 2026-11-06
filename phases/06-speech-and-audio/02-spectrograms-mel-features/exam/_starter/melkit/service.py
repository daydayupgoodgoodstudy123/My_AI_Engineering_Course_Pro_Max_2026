"""Glue used by the API layer: one front-end config, its features, and the shared cache."""
from __future__ import annotations

from .cache import FeatureCache, Features, clip_hash
from .cmvn import cmvn
from .config import fingerprint
from .deltas import add_deltas
from .features import log_mel_spectrogram


class FeatureService:
    def __init__(self, config: dict, cache: FeatureCache) -> None:
        self.config = config
        self.cache = cache
        self.config_id = fingerprint(config)
        self.computed = 0  # matrices computed here rather than read from the cache

    @property
    def width(self) -> int:
        """Values per frame: n_mels static values, plus n_mels for every delta order."""
        return self.config["mel"]["n_mels"] * (1 + len(self.config["deltas"]["windows"]))

    def features(self, samples: list[float], sample_rate: int) -> Features:
        """Features of one clip, read from the cache when this config has seen the clip before."""
        cfg = self.config
        if sample_rate != cfg["sample_rate"]:
            raise ValueError(
                f"this front end takes {cfg['sample_rate']} Hz audio, got {sample_rate} Hz; resample first"
            )
        clip_id = clip_hash(samples, sample_rate)
        cached = self.cache.get(clip_id, self.config_id)
        if cached is not None:
            if cached.n_feats != self.width:
                raise ValueError(
                    f"cached features have {cached.n_feats} values per frame, expected {self.width}"
                )
            return cached
        stft, mel, log = cfg["stft"], cfg["mel"], cfg["log"]
        frames = log_mel_spectrogram(
            samples,
            sample_rate,
            n_fft=stft["n_fft"],
            hop=stft["hop"],
            n_mels=mel["n_mels"],
            fmin=mel["fmin"],
            fmax=mel["fmax"],
            kind=log["kind"],
            floor=log["floor"],
        )
        frames = add_deltas(frames, cfg["deltas"]["windows"])
        if cfg["cmvn"]["mode"] == "utterance":
            frames = cmvn(frames, cfg["cmvn"]["floor"])
        elif cfg["cmvn"]["mode"] != "none":
            raise ValueError(f"cmvn mode must be 'utterance' or 'none', got {cfg['cmvn']['mode']!r}")
        feats = Features(self.width, frames)
        self.cache.put(clip_id, self.config_id, feats)
        self.computed += 1
        return feats
