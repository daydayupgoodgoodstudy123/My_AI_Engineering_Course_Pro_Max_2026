"""Moshi's acoustic delay: the acoustic codebooks run one frame behind the semantic one.

A frame is a dict of streams, and streams can be grouped in nested dicts. A stream is either
one token (like the text) or a list with one code per codebook. Delays, in frames, are written
in the same shape as the frames they apply to.
"""
from __future__ import annotations

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
    raise NotImplementedError


def undelay(steps: list[dict], delays: dict) -> list[dict]:
    """Undo delay(). Steps that delay() could not have produced for these delays raise ValueError."""
    raise NotImplementedError


def ready_ms(frame: int, delays: dict) -> int:
    """When the model's frame `frame` can start playing, in ms from the start of the session.

    A frame is complete once its most delayed codebook has been generated, and step s can only
    run once the user's frame s has fully arrived.
    """
    raise NotImplementedError
