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
    order = [paper.arxiv_id for paper in papers]
    titles = {paper.arxiv_id: " ".join(paper.title.split()) for paper in papers}
    listing = "\n".join(f"- {paper.arxiv_id} ({paper.year}): {titles[paper.arxiv_id]}" for paper in papers)
    yield _section("Search results", listing)

    arrived: dict[str, str | None] = {}
    sent = 0
    async for summary in summaries:
        if summary.arxiv_id not in titles:
            raise ValueError(f"a summary for {summary.arxiv_id!r}, which is not in the report")
        arrived.setdefault(summary.arxiv_id, summary.text)
        while sent < len(order) and order[sent] in arrived:
            yield _paper_section(order[sent], titles[order[sent]], arrived[order[sent]])
            sent += 1
    for arxiv_id in order[sent:]:
        yield _paper_section(arxiv_id, titles[arxiv_id], arrived.get(arxiv_id))

    missing = [arxiv_id for arxiv_id in order if arrived.get(arxiv_id) is None]
    conclusion = f"Summarized {len(order) - len(missing)} of {len(order)} papers."
    if missing:
        conclusion += f" Missing: {', '.join(missing)}."
    yield _section("Conclusion", conclusion)


def _section(heading: str, body: str) -> str:
    return f"## {heading}\n\n{body}\n\n"


def _paper_section(arxiv_id: str, title: str, text: str | None) -> str:
    return _section(f"{arxiv_id}: {title}", PLACEHOLDER if text is None else _escape(text))


def _escape(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        rest = line.lstrip(" ")
        if rest.startswith("#"):
            line = line[: len(line) - len(rest)] + "\\" + rest
        lines.append(line)
    return "\n".join(lines)
