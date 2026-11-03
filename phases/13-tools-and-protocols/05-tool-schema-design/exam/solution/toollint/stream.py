"""Lint a paginated registry in CI, logging findings as the pages arrive."""
from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from .releases import descriptor_digest
from .rules import Finding, lint_tool, summary_line


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
    seen: set[str] = set()
    reported: set[str] = set()
    logged: list[Finding] = []
    async for page in pages:
        for tool in page:
            name = tool.get("name", "")
            found: list[Finding] = []
            if name not in seen:
                seen.add(name)
            elif name not in reported:
                reported.add(name)
                found.append(Finding("block", name, "duplicate tool name"))
            if baseline is None or baseline.get(name) != descriptor_digest(tool):
                found.extend(lint_tool(tool))
            for finding in found:
                logged.append(finding)
                yield str(finding)
    yield summary_line(logged)
    yield "FAIL" if any(f.severity == "block" for f in logged) else "PASS"
