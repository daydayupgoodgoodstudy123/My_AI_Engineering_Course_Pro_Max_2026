"""Tiers 1 and 2 of the VAD cascade on a live stream."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable


async def cascade(
    chunks: AsyncIterator[list[float]],
    sample_rate: int,
    gate: Callable[[list[float]], bool],
    model: Callable[[list[float]], float],
    frame_ms: int = 20,
    context_frames: int = 3,
    speech_prob: float = 0.5,
) -> AsyncIterator[str]:
    """Run the cascade on audio as it arrives and report where speech starts and stops.

    The stream is cut into complete frames of frame_ms; chunks may have any size. Tier 1,
    gate(frame), runs on every frame. Only a frame the gate passes reaches Tier 2:
    model(context) is called once for it, where context is the samples of that frame preceded
    by up to context_frames - 1 earlier frames of the stream, whether or not the gate passed
    them. The frame is speech when the model returns at least speech_prob; a frame the gate
    rejects is not speech.

    The stream starts in silence. Each change is sent as a server-sent event as soon as
    the frame that causes it is complete, and one stats event follows the end of the stream:

        event: speech
        data: {"sample": <first sample of the first speech frame>}

        event: silence
        data: {"sample": <first sample of the first non-speech frame>}

        event: stats
        data: {"frames": <frames>, "model_calls": <model calls>, "skipped": <frames - model calls>}

    "skipped" counts the frames the gate kept away from the model.
    """
    raise NotImplementedError
