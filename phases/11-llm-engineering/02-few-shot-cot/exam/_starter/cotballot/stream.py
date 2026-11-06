"""NDJSON running ballots for asynchronously arriving reasoning samples."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from .ballot import tally_samples


def ballot_event(sample: dict, reasonings: list[str]) -> str:
    """Append one completed sample and encode its cumulative NDJSON ballot.

    reasonings is this batch's mutable arrival-ordered history. Append the
    exact current text once and use tally_samples on the resulting history.
    Preserve current sample_id/text. Emit index=attempted, the current sample's
    normalized answer (possibly None), and all cumulative attempted, valid,
    winner, confidence and votes fields. Confidence remains a fraction, not a
    percentage; votes contains the full distribution. Return one complete JSON
    object with exactly one terminal LF, even for an invalid answer. The async
    source loop, fresh per-stream history and source ownership are supplied.
    """
    raise NotImplementedError

async def stream_ballots(samples: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Given fresh batch history, source pull-through and early-close ownership.

    Publish the synchronous callback's complete event before pulling the next
    sample. The short batch retains its reasoning history without a fixed
    memory bound. Only ballot_event's domain history/event projection is TODO.
    """
    reasonings = []
    try:
        async for sample in samples:
            event = ballot_event(sample, reasonings)
            yield event
    finally:
        close = getattr(samples, "aclose", None)
        if close is not None:
            await close()
