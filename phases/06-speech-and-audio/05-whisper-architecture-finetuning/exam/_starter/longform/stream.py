"""Transcribe a live stream window by window, the way Whisper reads long audio."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from .tokens import Segment
from .windows import CHUNK_S, SAMPLE_RATE


def is_loop(text: str, ngram: int = 3, repeats: int = 3) -> bool:
    """True when some run of ngram words occurs repeats times or more in text.

    Words are compared without case or punctuation, so "Thanks for watching!" and
    "thanks, for watching" are the same three words.
    """
    raise NotImplementedError


async def transcribe_stream(
    chunks: AsyncIterator[list[float]],
    decode: Callable[[list[float], str | None], list[Segment]],
    sample_rate: int = SAMPLE_RATE,
    window_s: float = CHUNK_S,
) -> AsyncIterator[str]:
    """Transcribe a live stream in consecutive windows, each as soon as it is full.

    Chunks may have any size. decode(samples, previous) is the model: samples are one
    window of audio, and previous is the text kept since the last reset, fed back as
    context (None when there is none). When the stream ends, whatever is left is decoded
    as a last, shorter window.

    Each kept segment is sent as a server-sent event, "data: <json>" and a blank line,
    with {"start": seconds, "end": seconds, "text": text} timed from the start of the
    stream and rounded to 0.01 s. The stream ends with "data: [DONE]".

    A window whose text is a loop (is_loop) is a hallucination: send nothing for it, and
    reset the context so that its text never reaches a later window.
    """
    raise NotImplementedError
