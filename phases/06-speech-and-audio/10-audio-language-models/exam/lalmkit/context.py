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
    raise NotImplementedError
