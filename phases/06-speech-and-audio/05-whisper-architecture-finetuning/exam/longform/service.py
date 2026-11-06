"""Glue used by the API layer: plan the windows, decode each one, stitch the words."""
from __future__ import annotations

from collections.abc import Callable

from .stitch import stitch
from .tokens import Segment, parse
from .windows import Window, plan_windows


class LongformService:
    def __init__(self, decode_window: Callable[[Window], str], overlap_s: float = 5.0) -> None:
        """decode_window(window) runs Whisper on samples window.start:window.end, padded
        to 30 s, and returns the decoder's text with one timestamp pair per word."""
        self.decode_window = decode_window
        self.overlap_s = overlap_s

    def transcribe(self, n_samples: int) -> list[Segment]:
        """Words of a whole recording, timed from its start."""
        windows = plan_windows(n_samples, self.overlap_s)
        words = [parse(self.decode_window(window)).segments for window in windows]
        return stitch(windows, words)
