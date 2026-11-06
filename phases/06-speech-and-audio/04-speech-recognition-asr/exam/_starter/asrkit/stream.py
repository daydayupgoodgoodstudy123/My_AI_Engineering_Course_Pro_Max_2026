"""Greedy CTC decoding of a live stream of frames into word events."""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from .ctc import Frame


async def stream_words(
    chunks: AsyncIterator[Sequence[Frame]], frame_ms: int = 20
) -> AsyncIterator[str]:
    """Greedy-decode a live stream of frames into word events, each as soon as it is known.

    Chunks hold any number of frames, and the events are the same whatever the chunking.
    Every event is one Server-Sent Events message: an "event:" line, a "data:" line holding
    one JSON object, then a blank line.

    partial  {"text": the word so far}, each time the word being spoken gains a letter.
    final    {"text": word, "start_ms": int, "end_ms": int}, once a space token or the end
             of the stream closes the word. start_ms is where the word's first letter frame
             begins and end_ms where its last letter frame ends, at frame_ms per frame.
    """
    raise NotImplementedError
