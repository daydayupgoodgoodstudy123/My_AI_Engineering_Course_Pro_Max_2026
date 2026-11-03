"""Lint a paginated registry in CI, logging findings as the pages arrive."""
from __future__ import annotations

from collections.abc import AsyncIterator, Mapping


async def lint_stream(
    pages: AsyncIterator[list[dict]],
    baseline: Mapping[str, str] | None = None,
) -> AsyncIterator[str]:
    """Lint a registry that arrives a page of tools at a time, and log the result for CI.

    Yields one log line per finding, str(finding), as soon as its tool has been checked: the
    findings lint_tool gives, in that order. A name seen earlier in the stream is reported once,
    as a block "duplicate tool name" finding just before the findings of its second occurrence.

    baseline is the manifest of the release before ({tool name: descriptor digest}). A tool whose
    digest matches its entry has not changed and is not linted again, but it still counts when
    looking for duplicate names.

    After the last page come two more lines: summary_line() over every finding logged, then the
    verdict, FAIL if any of them is a block finding and PASS otherwise. Lines carry no line break.
    """
    raise NotImplementedError
