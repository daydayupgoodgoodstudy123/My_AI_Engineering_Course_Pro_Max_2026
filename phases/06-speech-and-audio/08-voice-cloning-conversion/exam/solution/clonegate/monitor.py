"""Watch a live audio stream for the CloneGate watermark."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from .watermark import Detection, Watermarker, bits_to_int


async def watch(
    chunks: AsyncIterator[list[float]],
    watermarker: Watermarker,
    sample_rate: int,
    check_s: float = 0.1,
) -> AsyncIterator[str]:
    """Emit exactly one Server-Sent Event for the stream, as early as the evidence allows.

    Evidence accumulates from the start of the stream. It is scored after every check_s
    seconds of audio, counted in samples from the start of the stream, and once more when the
    stream ends. At the first score where the mark is found, emit

        event: watermark
        data: {"payload": <int>, "at": <seconds of audio read>}

    and stop reading the stream. If the stream ends first, emit

        event: unmarked
        data: {"seconds": <seconds of audio read>}

    Every event ends with a blank line.
    """
    step = round(check_s * sample_rate)
    if step <= 0:
        raise ValueError("check_s is shorter than one sample")
    evidence = watermarker.evidence()
    async for chunk in chunks:
        pos = 0
        while pos < len(chunk):
            take = step - evidence.samples % step
            evidence.add(chunk[pos : pos + take])
            pos += take
            if evidence.samples % step == 0:
                verdict = watermarker.verdict(evidence)
                if verdict.found:
                    yield _watermark(verdict, evidence.samples / sample_rate)
                    return
    verdict = watermarker.verdict(evidence)
    if verdict.found:
        yield _watermark(verdict, evidence.samples / sample_rate)
    else:
        yield _event("unmarked", {"seconds": evidence.samples / sample_rate})


def _watermark(verdict: Detection, at: float) -> str:
    return _event("watermark", {"payload": bits_to_int(verdict.bits), "at": at})


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"
