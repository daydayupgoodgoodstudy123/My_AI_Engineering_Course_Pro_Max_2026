"""Keep a live audio + text conversation inside the model's context budget."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .inputs import AUDIO_BOS, AUDIO_EOS, AUDIO_PAD, clip_tokens


@dataclass(frozen=True)
class AudioChunk:
    num_samples: int  # 16 kHz samples that just arrived from the microphone


@dataclass(frozen=True)
class Turn:
    role: str  # "system", "user" or "assistant"
    ids: list[int]  # the turn's text tokens


class _Clip:
    """A run of consecutive audio chunks, and how many of its tokens were dropped from the front."""

    def __init__(self) -> None:
        self.samples = 0
        self.dropped = 0

    def tokens(self) -> int:
        return clip_tokens(self.samples) - self.dropped


async def live_context(
    events: AsyncIterator[AudioChunk | Turn], budget: int
) -> AsyncIterator[list[int]]:
    """After every event, yield the ids the model would see if it were called now.

    Everything stays in arrival order. A turn appears as its ids. Consecutive audio chunks form
    one clip, which appears as AUDIO_BOS, one AUDIO_PAD per audio token of the clip so far
    (inputs.clip_tokens), and AUDIO_EOS.

    The context never holds more than `budget` ids. When it would, the oldest audio goes first:
    tokens are dropped from the front of the oldest clip, and a clip left with no tokens goes
    with its two markers. Only when no audio is left are turns dropped, oldest first; the system
    turn and the turn that just arrived always stay. If those two alone exceed the budget, raise
    ValueError.
    """
    segments: list[Turn | _Clip] = []
    clip: _Clip | None = None  # the clip that the next audio chunk extends
    async for event in events:
        if isinstance(event, AudioChunk):
            if clip is None:
                clip = _Clip()
                segments.append(clip)
            clip.samples += event.num_samples
        else:
            clip = None
            segments.append(event)
        _fit(segments, budget, event)
        yield _render(segments)


def _cost(segment: Turn | _Clip) -> int:
    if isinstance(segment, Turn):
        return len(segment.ids)
    tokens = segment.tokens()
    return tokens + 2 if tokens else 0


def _fit(segments: list[Turn | _Clip], budget: int, newest: AudioChunk | Turn) -> None:
    over = sum(_cost(segment) for segment in segments) - budget
    for segment in segments:  # audio first, oldest clip first, from the front of the clip
        if over <= 0:
            return
        if isinstance(segment, _Clip) and segment.tokens():
            take = min(over, segment.tokens())
            emptied = take == segment.tokens()
            segment.dropped += take
            over -= take + (2 if emptied else 0)
    i = 0
    while over > 0 and i < len(segments):  # then turns, oldest first
        segment = segments[i]
        if isinstance(segment, Turn) and segment.role != "system" and segment is not newest:
            del segments[i]
            over -= len(segment.ids)
        else:
            i += 1
    if over > 0:
        raise ValueError(f"a budget of {budget} ids cannot hold the system turn and the newest turn")


def _render(segments: list[Turn | _Clip]) -> list[int]:
    ids: list[int] = []
    for segment in segments:
        if isinstance(segment, Turn):
            ids += segment.ids
        elif segment.tokens():
            ids += [AUDIO_BOS] + [AUDIO_PAD] * segment.tokens() + [AUDIO_EOS]
    return ids
