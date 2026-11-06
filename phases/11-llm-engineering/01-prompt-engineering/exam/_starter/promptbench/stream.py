"""CSV score rows for an asynchronously arriving sequence of replay cases."""
from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator

from .scoring import compare_models


COLUMNS = ("case_id", "pattern", "model", "response", "composite_score", "tokens", "latency_ms")


def _row(values) -> str:
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\r\n").writerow(values)
    return buffer.getvalue()


def score_rows(case: dict) -> list[str]:
    """Project one complete replay case into CSV model-score records.

    Use this case's criteria with compare_models. Preserve input model order,
    including models with zero token usage. Each record contains the case id,
    pattern, current model name, exact raw response, composite score, token
    count and original API latency in milliseconds. CSV quoting is supplied by
    _row; do not modify the case or its replay results. The complete async
    header, source pull-through and source ownership are already supplied.
    """
    raise NotImplementedError

async def stream_scores(cases: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Given CSV header, per-case dispatch, publication and source ownership.

    All records returned for the current case are published before the next
    source pull. Only synchronous score_rows is candidate work. A case's model
    rows are buffered together; there is no bounded-per-case memory claim.
    """
    try:
        yield _row(COLUMNS)
        async for case in cases:
            for row in score_rows(case):
                yield row
    finally:
        close = getattr(cases, "aclose", None)
        if close is not None:
            await close()
