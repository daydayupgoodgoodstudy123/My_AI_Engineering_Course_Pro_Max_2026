"""Glue used by the API layer: text to phones, phones to frames, streams and SSML."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .duration import allocate_frames, predict_durations
from .g2p import frontend
from .lexicon import PronunciationLexicon
from .ssml import flatten
from .stream import speech_events


class TTSService:
    def __init__(self, lexicon: PronunciationLexicon, hop_ms: float = 12.5) -> None:
        self.lexicon = lexicon
        self.hop_ms = hop_ms

    def phonemes(self, text: str) -> list[str]:
        """Phones for one utterance, with the preferred pronunciation of every known word."""
        return frontend(text, self.lexicon.table())

    def schedule(self, text: str, speed: float = 1.0) -> list[tuple[str, int, int]]:
        """(phone, first frame, end frame) for every phone, at the given speaking speed."""
        phones = self.phonemes(text)
        frames = allocate_frames(predict_durations(phones, self.hop_ms, speed), self.hop_ms)
        spans: list[tuple[str, int, int]] = []
        start = 0
        for phone, count in zip(phones, frames):
            spans.append((phone, start, start + count))
            start += count
        return spans

    def stream(self, deltas: AsyncIterator[str]) -> AsyncIterator[str]:
        """Speakable chunks of streaming text; speech_events defines the wire format."""
        return speech_events(deltas)

    def render(self, ssml: str) -> list[dict]:
        """Segments of an SSML document, ready to synthesize one by one."""
        return flatten(ssml)
