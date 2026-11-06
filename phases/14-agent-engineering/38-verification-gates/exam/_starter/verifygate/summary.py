"""A Markdown summary of the verification report, kept current while feedback records arrive."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable


def render_summary(report: dict) -> str:
    r"""The Markdown summary of one verification report (Verdict.to_dict()), for a PR comment.

    It reads, line by line:

        # T-42: FAILED
        head 4be7a1c, strict

        ## block (2)

        | code | detail |
        | --- | --- |
        | acceptance.failed | exit 1: pytest -x tests/test\_signup.py |

    The first line is the task id and PASSED or FAILED, the second the head commit, with ", strict"
    when the gate ran strict. Then comes one section per severity that has findings, in the order
    block, warn, info, overridden: a blank line, the heading with the number of findings, a blank
    line and the table, its rows in report order. The overridden table has two more columns,
    | code | detail | by | reason |, filled from overridden_by and override_reason.
    In every cell, each backslash is first written as \\, then each of ` * _ | gets a backslash in
    front of it; nothing else changes. Every line ends with a newline.
    """
    raise NotImplementedError


async def stream_summaries(
    records: AsyncIterator[dict],
    gate: Callable[[list[dict]], dict],
) -> AsyncIterator[str]:
    r"""Re-run the gate as feedback records arrive, and stream the summary each time it changes.

    gate(feedback) takes the records so far, in arrival order, and returns the report as
    Verdict.to_dict() would. The first summary is the one for no records at all, sent before the
    first record is read, so a stream without records still gets that one. After that the gate runs
    once per record, and a summary goes out as soon as a record changes it; a record that leaves the
    summary as it was sends nothing.

    Each yielded string is one summary. Two summaries are separated by a blank line, a line "---" and
    a blank line (a thematic break: without the blank line before it, Markdown reads "---" as a
    heading underline), so every summary but the first starts with "\n---\n\n". There is no break
    before the first summary or after the last.
    """
    raise NotImplementedError
