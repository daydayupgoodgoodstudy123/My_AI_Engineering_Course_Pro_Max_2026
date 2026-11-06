"""Greedy CTC decoding of a live stream of frames into word events."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

from .ctc import BLANK, SPACE, VOCAB, Frame, argmax


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
    prev = None  # most likely token of the previous frame, kept across chunks
    word = ""
    start = end = 0  # frame indices: the word's first letter frame, one past its last
    index = 0  # frames seen over the whole stream
    async for chunk in chunks:
        for frame in chunk:
            token = argmax(frame)
            if token == SPACE:
                if word:
                    yield _final(word, start, end, frame_ms)
                    word = ""
            elif token != BLANK:
                if token != prev:
                    if not word:
                        start = index
                    word += VOCAB[token]
                    yield _event("partial", {"text": word})
                end = index + 1
            prev = token
            index += 1
    if word:
        yield _final(word, start, end, frame_ms)


def _final(word: str, start: int, end: int, frame_ms: int) -> str:
    return _event("final", {"text": word, "start_ms": start * frame_ms, "end_ms": end * frame_ms})


def _event(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data)}\n\n"
