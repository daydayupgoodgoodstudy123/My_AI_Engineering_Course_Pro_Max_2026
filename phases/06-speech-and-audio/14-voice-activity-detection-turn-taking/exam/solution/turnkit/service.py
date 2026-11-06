"""Glue used by the voice agent: gate, turn detector, segment table, STT flush and live stream."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from .cascade import cascade
from .energy import energy_gate, rms
from .segments import Segment, SegmentTable
from .turns import TurnDetector


class TurnService:
    def __init__(
        self,
        table: SegmentTable,
        sample_rate: int,
        stt=None,
        threshold_dbfs: float = -40.0,
        frame_ms: int = 20,
        hangover_ms: int = 100,
        min_speech_ms: int = 250,
        silence_hangover_ms: int = 500,
        pre_roll_ms: int = 300,
    ) -> None:
        self.table = table
        self.sample_rate = sample_rate
        self.stt = stt
        self.threshold_dbfs = threshold_dbfs
        self.frame_ms = frame_ms
        self.hangover_ms = hangover_ms
        self.min_speech_ms = min_speech_ms
        self.silence_hangover_ms = silence_hangover_ms
        self.pre_roll_ms = pre_roll_ms

    def listen(self, recording: str, signal: list[float]) -> list[Segment]:
        """Find the turns in a recording, store them, and hand each finished turn to the STT.

        The flush trick: as soon as a turn ends, its audio goes to the STT followed by a flush,
        so the transcript does not wait for the STT's look-ahead.
        """
        frame_len = self.sample_rate * self.frame_ms // 1000
        detector = TurnDetector(
            self.sample_rate, frame_len, self.min_speech_ms, self.silence_hangover_ms, self.pre_roll_ms
        )
        flags = energy_gate(signal, self.sample_rate, self.threshold_dbfs, self.frame_ms, self.hangover_ms)
        events = [detector.update(flag) for flag in flags] + [detector.flush()]
        turns: list[Segment] = []
        start = 0
        for event in events:
            if event is None:
                continue
            if event.kind == "start":
                start = event.sample
                continue
            turns.append(self.table.add(recording, self.sample_rate, start, event.sample))
            if self.stt is not None:
                self.stt.send_audio(signal[start : event.sample])
                self.stt.send_flush()
        return turns

    def stream(
        self, chunks: AsyncIterator[list[float]], model: Callable[[list[float]], float]
    ) -> AsyncIterator[str]:
        """Run the gate and a VAD model over a live stream; cascade defines the wire format."""
        limit = 10.0 ** (self.threshold_dbfs / 20.0)
        return cascade(chunks, self.sample_rate, lambda frame: rms(frame) > limit, model, self.frame_ms)
