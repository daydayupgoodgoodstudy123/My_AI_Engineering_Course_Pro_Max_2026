"""Running error rates, per domain, while an eval job's results arrive."""
from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from dataclasses import dataclass

HEADER = ("seen", "domain", "utterances", "rate")
POOLED = "*"


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
    if every < 1:
        raise ValueError("every must be at least 1")
    out = io.StringIO()
    writer = csv.writer(out)

    def drain() -> str:
        text = out.getvalue()
        out.seek(0)
        out.truncate()
        return text

    totals: dict[str, list[int]] = {}  # domain -> [utterances, errors, units]
    seen = reported = 0

    def report() -> None:
        pooled = [0, 0, 0]
        for domain in sorted(totals):
            tally = totals[domain]
            writer.writerow((seen, domain, tally[0], str(tally[1] / tally[2])))
            pooled = [a + b for a, b in zip(pooled, tally)]
        writer.writerow((seen, POOLED, pooled[0], str(pooled[1] / pooled[2])))

    writer.writerow(HEADER)
    yield drain()
    async for batch in batches:
        for result in batch:
            tally = totals.setdefault(result.domain, [0, 0, 0])
            tally[0] += 1
            tally[1] += result.errors
            tally[2] += result.units
            seen += 1
            if seen % every == 0:
                report()
                reported = seen
                yield drain()
    if seen != reported:
        report()
        yield drain()
