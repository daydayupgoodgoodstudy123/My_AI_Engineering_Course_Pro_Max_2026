"""Join the transcripts of overlapping windows into one transcript of the recording."""
from __future__ import annotations

from .tokens import Segment
from .windows import Window


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
    raise NotImplementedError
