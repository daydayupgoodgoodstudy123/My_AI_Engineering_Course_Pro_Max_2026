"""Mic side of the loop: callback chunks in, whole frames out."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .meter import rms_dbfs
from .ring import RingBuffer


def ms_to_samples(ms: int, sample_rate: int) -> int:
    """Whole samples in ms milliseconds of audio at sample_rate."""
    return sample_rate // 1000 * ms


@dataclass(frozen=True)
class Frame:
    t_ns: int  # capture time of the first sample, in ns since the stream started
    samples: list[float]
    dbfs: float


class Capture:
    """The audio callback calls write() with chunks of any size; the processing loop calls
    frames() to take every whole frame that has arrived.

    At most buffer_ms of audio waits in the ring. When the loop falls behind, the oldest
    audio is dropped, and the frames after the gap keep their own capture time.
    """

    def __init__(self, sample_rate: int, frame_ms: int = 20, buffer_ms: int = 2000) -> None:
        self.sample_rate = sample_rate
        self.frame_len = ms_to_samples(frame_ms, sample_rate)
        self.ring = RingBuffer(ms_to_samples(buffer_ms, sample_rate))

    def write(self, chunk: Sequence[float]) -> None:
        self.ring.write(chunk)

    def frames(self) -> list[Frame]:
        out = []
        while self.ring.level() >= self.frame_len:
            t_ns = self.ring.position * 1_000_000_000 // self.sample_rate
            samples = self.ring.read(self.frame_len)
            out.append(Frame(t_ns, samples, rms_dbfs(samples)))
        return out
