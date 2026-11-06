"""Per-turn latency reports from a live voice-pipeline trace."""
from __future__ import annotations

from collections.abc import AsyncIterator


async def turn_reports(events: AsyncIterator[dict], max_delay_ms: int) -> AsyncIterator[str]:
    """Report each turn of a live trace as a server-sent event, as soon as the turn is complete.

    Every event has "ms" (when it happened), "turn" and "type": vad.start and vad.end (the user's
    speech), stt.partial and stt.final (with "text"), llm.token, tts.audio (a chunk of assistant
    audio starts playing), user.barge_in (the user cut in while the assistant was talking) and
    turn.end (the turn's last event). Events come from several components and arrive out of order,
    but no event arrives after one that is max_delay_ms or more newer than it. A turn is complete
    once an event at least max_delay_ms newer than its turn.end has arrived, or when the stream
    ends. Turns end in the order they start, so reports come out in turn order.

    A turn the user spoke is reported as
        event: turn
        data: {"turn": n, "text": ..., "first_audio_ms": ..., "barge_in_ms": ...}
    text is the stt.final transcript. first_audio_ms runs from vad.end to the first tts.audio.
    barge_in_ms is how long the assistant kept talking after user.barge_in: the last tts.audio at or
    after it, minus the barge-in, or 0 when no audio followed. Either is null without those events.

    A turn with no vad.start is the STT transcribing silence. It is reported as
        event: hallucination
        data: {"turn": n, "text": ...}

    Every server-sent event ends with a blank line.
    """
    raise NotImplementedError
