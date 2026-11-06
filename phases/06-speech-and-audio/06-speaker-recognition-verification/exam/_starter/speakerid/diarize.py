"""Online diarization: who spoke when, decided segment by segment as the speech arrives."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .embed import cosine, l2_normalize


@dataclass(frozen=True)
class Segment:
    """One speech segment from the VAD, with its speaker embedding. Times are in seconds."""

    start: float
    end: float
    embedding: list[float]


async def diarize_stream(
    segments: AsyncIterator[Segment], threshold: float, file_id: str = "meeting"
) -> AsyncIterator[str]:
    """Assign each arriving segment to a speaker and stream the speaker turns as RTTM lines.

    Segments arrive in time order. A speaker's centroid is the mean of the unit-length embeddings
    of the segments assigned to them so far. Each segment joins the speaker whose centroid is
    most cosine-similar to it, if that similarity is at least threshold, and otherwise starts a
    new speaker. Speakers are named spk0, spk1, ... in order of appearance.

    Consecutive segments of the same speaker form one turn, from the first one's start to the
    last one's end. Write a turn as soon as it is over, and the last turn when the stream ends,
    each as one newline-terminated RTTM line:
    SPEAKER <file_id> 1 <onset> <duration> <NA> <NA> <speaker> <NA> <NA>
    with onset and duration in seconds, three decimals.
    """
    raise NotImplementedError
