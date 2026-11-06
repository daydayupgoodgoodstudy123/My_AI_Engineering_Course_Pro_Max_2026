"""Running error rates, per domain, while an eval job's results arrive."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Scored:
    utterance: str
    domain: str  # the slice the utterance belongs to, e.g. "accented" or "far-field"
    errors: int
    units: int  # reference words, or characters for CER


async def stream_report(
    batches: AsyncIterator[list[Scored]], every: int = 100
) -> AsyncIterator[str]:
    """Report corpus error rates per domain as results arrive, as CSV text.

    The first line is the header seen,domain,utterances,rate. After every `every` utterances,
    and after the last one unless it was just reported, write one row per domain seen so far,
    sorted by domain, then a row with domain "*" for all of them together. seen counts the
    utterances so far, utterances those in the row's domain, and rate is the domain's corpus
    error rate, its summed errors over its summed units, written with str(). Batches may have
    any size. Rows use the csv module's default dialect.
    """
    raise NotImplementedError
