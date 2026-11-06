"""Moshi's acoustic delay: the acoustic codebooks run one frame behind the semantic one.

A frame is a dict of streams, and streams can be grouped in nested dicts. A stream is either
one token (like the text) or a list with one code per codebook. Delays, in frames, are written
in the same shape as the frames they apply to.
"""
from __future__ import annotations

from .mimi import FRAME_MS
from .tokens import CODEBOOKS, UNSET

MOSHI_DELAYS = {
    "text": 0,
    "model": [0] + [1] * (CODEBOOKS - 1),
    "user": [0] + [1] * (CODEBOOKS - 1),
}


def delay(frames: list[dict], delays: dict) -> list[dict]:
    """Lay frames out as delayed steps: step s holds frame s - d of a stream delayed by d.

    There are len(frames) + (the largest delay) steps, so the last frame's most delayed codebook
    still gets a step, and each step has the same nested shape as a frame. A position with no
    frame to fill it (before a delayed stream starts, after a stream ends) holds UNSET. No frames,
    no steps. A frame that does not match the delays' shape (a stream or a codebook missing or
    extra, a token that is not an int >= 0) raises ValueError.
    """
    longest = _longest(delays)
    for frame in frames:
        _check(frame, delays, unset_ok=False)
    if not frames:
        return []
    return [_shift(delays, frames, s) for s in range(len(frames) + longest)]


def undelay(steps: list[dict], delays: dict) -> list[dict]:
    """Undo delay(). Steps that delay() could not have produced for these delays raise ValueError."""
    if not steps:
        return []
    count = len(steps) - _longest(delays)
    if count < 1:
        raise ValueError(f"{len(steps)} steps are too few for these delays")
    for step in steps:
        _check(step, delays, unset_ok=True)
    frames = [_gather(delays, steps, t) for t in range(count)]
    if delay(frames, delays) != steps:
        raise ValueError("these steps are not a delayed layout for these delays")
    return frames


def ready_ms(frame: int, delays: dict) -> int:
    """When the model's frame `frame` can start playing, in ms from the start of the session.

    A frame is complete once its most delayed codebook has been generated, and step s can only
    run once the user's frame s has fully arrived.
    """
    return (frame + _longest(delays) + 1) * FRAME_MS


def _shift(spec, frames: list[dict], s: int, path: tuple = ()):
    """Step s of the streams under `path`: every position holds its token from frame s - delay."""
    if isinstance(spec, dict):
        return {key: _shift(sub, frames, s, path + (key,)) for key, sub in spec.items()}
    if isinstance(spec, list):
        return [_at(frames, s - d, path + (k,)) for k, d in enumerate(spec)]
    return _at(frames, s - spec, path)


def _gather(spec, steps: list[dict], t: int, path: tuple = ()):
    """Frame t of the streams under `path`: every position comes from step t + delay."""
    if isinstance(spec, dict):
        return {key: _gather(sub, steps, t, path + (key,)) for key, sub in spec.items()}
    if isinstance(spec, list):
        return [_at(steps, t + d, path + (k,)) for k, d in enumerate(spec)]
    return _at(steps, t + spec, path)


def _at(rows: list[dict], i: int, path: tuple):
    if not 0 <= i < len(rows):
        return UNSET
    node = rows[i]
    for key in path:
        node = node[key]
    return node


def _longest(spec) -> int:
    if isinstance(spec, dict):
        return max((_longest(sub) for sub in spec.values()), default=0)
    if isinstance(spec, list):
        return max((_longest(d) for d in spec), default=0)
    if _is_int(spec) and spec >= 0:
        return spec
    raise ValueError(f"a delay is an int >= 0, got {spec!r}")


def _check(node, spec, unset_ok: bool) -> None:
    if isinstance(spec, dict):
        if not isinstance(node, dict) or node.keys() != spec.keys():
            raise ValueError(f"expected the streams {list(spec)}, got {node!r}")
        for key, sub in spec.items():
            _check(node[key], sub, unset_ok)
    elif isinstance(spec, list):
        if not isinstance(node, list) or len(node) != len(spec):
            raise ValueError(f"expected {len(spec)} codebooks, got {node!r}")
        for value in node:
            _check(value, 0, unset_ok)
    elif not (_is_int(node) and (node >= 0 or (unset_ok and node == UNSET))):
        raise ValueError(f"expected a token, got {node!r}")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
