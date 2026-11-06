"""Tier 3 of the cascade: the turn-end state machine, with pre-roll and flush."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnEvent:
    kind: str  # "start" or "end"
    sample: int  # where the turn's audio starts or ends
    decided: int  # stream position, in samples, at which the detector knew


class TurnDetector:
    """Decide when a user starts and finishes a turn, one VAD frame at a time.

    Frame i covers samples [i * frame_len, (i + 1) * frame_len). Durations in ms become
    samples as ms * sample_rate // 1000.

    - A turn starts once a run of consecutive speech frames lasts at least min_speech_ms.
      The "start" event is decided at the end of that frame. Its sample is pre_roll_ms before
      the run's first frame, but never before sample 0 or the end of the previous turn.
    - A turn ends once a run of consecutive non-speech frames lasts at least
      silence_hangover_ms. The "end" event is decided at the end of that frame. Its sample is
      the end of the turn's last speech frame.
    """

    def __init__(
        self,
        sample_rate: int,
        frame_len: int,
        min_speech_ms: int = 250,
        silence_hangover_ms: int = 500,
        pre_roll_ms: int = 300,
    ) -> None:
        self.frame_len = frame_len
        self.min_speech = min_speech_ms * sample_rate // 1000
        self.silence_hangover = silence_hangover_ms * sample_rate // 1000
        self.pre_roll = pre_roll_ms * sample_rate // 1000
        self.position = 0  # samples seen so far
        self.speaking = False
        self.run = 0  # samples in the current run of speech (idle) or silence (speaking) frames
        self.run_start = 0  # first sample of that run
        self.floor = 0  # pre-roll never reaches before this sample

    def update(self, is_speech: bool) -> TurnEvent | None:
        """Feed the next frame's VAD decision and return the event it causes, if any."""
        frame_start = self.position
        self.position += self.frame_len
        if not self.speaking:
            if not is_speech:
                self.run = 0
                return None
            if self.run == 0:
                self.run_start = frame_start
            self.run += self.frame_len
            if self.run < self.min_speech:
                return None
            self.speaking = True
            self.run = 0
            return TurnEvent("start", max(self.run_start - self.pre_roll, self.floor), self.position)
        if is_speech:
            self.run = 0
            return None
        if self.run == 0:
            self.run_start = frame_start
        self.run += self.frame_len
        if self.run < self.silence_hangover:
            return None
        return self._end(self.run_start)

    def flush(self) -> TurnEvent | None:
        """End an open turn now, at the end of its last speech frame, without waiting for the hangover.

        The end event is decided at the current position. Speech that has not yet lasted
        min_speech_ms is dropped. Call it when the stream closes, or when something else
        (a semantic end-of-turn model, push-to-talk) says the user is done.
        """
        if not self.speaking:
            self.run = 0
            return None
        return self._end(self.run_start if self.run else self.position)

    def _end(self, end: int) -> TurnEvent:
        self.speaking = False
        self.run = 0
        self.floor = end
        return TurnEvent("end", end, self.position)
