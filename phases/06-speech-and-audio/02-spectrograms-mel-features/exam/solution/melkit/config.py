"""Front-end configs: nested dicts layered from defaults, model and run settings."""
from __future__ import annotations

import copy
import hashlib
import json

DEFAULTS: dict = {
    "sample_rate": 16000,
    "stft": {"n_fft": 400, "hop": 160},
    "mel": {"n_mels": 80, "fmin": 0.0, "fmax": None},
    "log": {"kind": "log", "floor": 1e-10},
    "deltas": {"windows": [2, 2]},
    "cmvn": {"mode": "utterance", "floor": 1e-8},
}


def merge(base: dict, *overrides: dict) -> dict:
    """Layer overrides onto base, left to right, and return a new config.

    Nested dicts merge key by key. Any other value (number, string, None, list) replaces
    the value below it whole; lists are never concatenated or merged item by item. A key
    that the layer below does not have raises KeyError naming its dotted path, such as
    "mel.n_mel", so a typo cannot silently fall back to the default. The inputs are left
    untouched and share nothing with the result.
    """
    result = copy.deepcopy(base)
    for override in overrides:
        _merge_into(result, override, "")
    return result


def _merge_into(target: dict, override: dict, prefix: str) -> None:
    for key, value in override.items():
        path = prefix + str(key)
        if key not in target:
            raise KeyError(f"unknown config key {path!r}")
        if isinstance(target[key], dict) and isinstance(value, dict):
            _merge_into(target[key], value, path + ".")
        else:
            target[key] = copy.deepcopy(value)


def fingerprint(config: dict) -> str:
    """Hex digest identifying a config by content.

    Configs that differ only in key order, at any depth, get the same fingerprint; any
    other change, including the order of a list, gives a different one. The value is the
    same in every process, so it can key an on-disk cache.
    """
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
