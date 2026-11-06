"""Join the transcripts of overlapping windows into one transcript of the recording."""
from __future__ import annotations

from .tokens import Segment
from .windows import HOP_LENGTH, SAMPLE_RATE, Window


def stitch(windows: list[Window], words: list[list[Segment]]) -> list[Segment]:
    """Join per-window word timings into one transcript.

    words[k] holds window k's words, timed in seconds from the start of that window. The
    result is timed in seconds from the start of the recording, rounded to 0.01 s.

    Neighbouring windows overlap, and each overlap is split at its midpoint: a word
    belongs to the window on whose side of the split its midpoint falls (a midpoint
    exactly on the split belongs to the later window). The start of the first window and
    the end of the last one have no neighbour, so nothing is trimmed there.

    A word that starts at or after the end of its window's real audio (positions * 0.02 s)
    was decoded from the padding, and is dropped.
    """
    if len(windows) != len(words):
        raise ValueError("need one word list per window")
    result: list[Segment] = []
    for k, (window, segments) in enumerate(zip(windows, words)):
        # Twice the split points, in samples, so every comparison is between integers.
        low = windows[k - 1].end + window.start if k > 0 else None
        high = window.end + windows[k + 1].start if k + 1 < len(windows) else None
        audio_end = window.positions * 2 * HOP_LENGTH
        for segment in segments:
            start = round(segment.start * SAMPLE_RATE)
            end = round(segment.end * SAMPLE_RATE)
            if start >= audio_end:
                continue
            midpoint = 2 * window.start + start + end
            if (low is not None and midpoint < low) or (high is not None and midpoint >= high):
                continue
            result.append(Segment(
                round((window.start + start) / SAMPLE_RATE, 2),
                round((window.start + end) / SAMPLE_RATE, 2),
                segment.text,
            ))
    return result
