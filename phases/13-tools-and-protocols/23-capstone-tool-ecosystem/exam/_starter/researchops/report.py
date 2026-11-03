"""The Markdown report, streamed section by section while the writer agent's summaries arrive."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .catalog import Paper

PLACEHOLDER = "_No summary: the writer agent did not return one._"


@dataclass(frozen=True)
class Summary:
    arxiv_id: str
    text: str | None  # None when the delegation failed


async def stream_report(papers: list[Paper], summaries: AsyncIterator[Summary]) -> AsyncIterator[str]:
    """Yield the report as Markdown text, one section at a time, always in the same order.

    The sections are "## Search results", with a line "- <arxiv_id> (<year>): <title>" per paper;
    then "## <arxiv_id>: <title>" for each paper, in the order given, with its summary as the
    body; then "## Conclusion", which reads "Summarized <k> of <n> papers." and, when any are
    missing, " Missing: <their ids, comma separated, in paper order>."

    summaries arrive as the writer agent finishes them, in any order. A section goes out as soon
    as it and every section before it are complete; a later section waits until then. A paper
    whose summary failed (text None) or never arrived by the end of the stream gets PLACEHOLDER.

    Headings and list lines stay on one line: every run of whitespace in a title becomes a single
    space. A summary line that starts with # after any spaces gets a backslash before that #, so
    a summary never opens a section of its own.
    """
    raise NotImplementedError
