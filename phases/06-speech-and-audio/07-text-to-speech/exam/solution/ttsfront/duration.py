"""Phone durations and the whole mel frames they become (lesson: duration, mel_schedule)."""
from __future__ import annotations

import math
from fractions import Fraction

# Typical durations in frames at a 12.5 ms hop, the lesson's table.
DURATION_FRAMES = {
    "AA": 9, "AE": 7, "AH": 6, "AO": 8, "AW": 9, "AY": 8, "B": 4, "CH": 6,
    "D": 4, "DH": 5, "EH": 6, "ER": 7, "EY": 8, "F": 6, "G": 5, "HH": 4,
    "IH": 5, "IY": 7, "JH": 6, "K": 5, "L": 5, "M": 5, "N": 5, "NG": 6,
    "OW": 8, "OY": 9, "P": 5, "R": 5, "S": 6, "SH": 7, "T": 4, "TH": 5,
    "UH": 6, "UW": 8, "V": 5, "W": 5, "Y": 5, "Z": 6, "ZH": 7,
    "_": 3,
    "_SHORT_": 6,
    "_PAUSE_": 12,
}


def predict_durations(phones: list[str], hop_ms: float = 12.5, speed: float = 1.0) -> list[float]:
    """Milliseconds per phone from the duration table. speed 1.25 speaks 25% faster."""
    if speed <= 0:
        raise ValueError("speed must be positive")
    return [DURATION_FRAMES.get(phone, 5) * hop_ms / speed for phone in phones]


def allocate_frames(durations_ms: list[float], hop_ms: float = 12.5) -> list[int]:
    """Whole mel frames for each phone that keep the utterance's total length.

    A phone's share is its duration in frames, but never less than one frame. The total
    is the sum of the shares, rounded half up. Each phone first gets the whole part of
    its share; the frames still missing go one each to the phones with the largest
    remainders, ties to the earlier phone.
    """
    hop = Fraction(hop_ms)
    if hop <= 0:
        raise ValueError("hop_ms must be positive")
    shares: list[Fraction] = []
    for duration in durations_ms:
        # Exact arithmetic: 30 ms and 55 ms both leave 0.4 of a frame, and float noise
        # must not decide which of them gets the leftover frame.
        share = Fraction(duration) / hop
        if share < 0:
            raise ValueError(f"negative duration {duration}")
        shares.append(max(Fraction(1), share))
    total = math.floor(sum(shares) + Fraction(1, 2))
    frames = [math.floor(share) for share in shares]
    order = sorted(range(len(shares)), key=lambda i: (frames[i] - shares[i], i))
    for i in order[: total - sum(frames)]:
        frames[i] += 1
    return frames
