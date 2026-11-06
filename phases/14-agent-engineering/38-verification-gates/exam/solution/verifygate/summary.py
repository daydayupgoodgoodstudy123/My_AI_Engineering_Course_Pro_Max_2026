"""A Markdown summary of the verification report, kept current while feedback records arrive."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

SECTIONS = ("block", "warn", "info", "overridden")
ESCAPED = "\\`*_|"
BREAK = "\n---\n\n"


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
    lines = [
        f"# {report['task_id']}: {'PASSED' if report['passed'] else 'FAILED'}",
        f"head {report['head_commit']}" + (", strict" if report["strict"] else ""),
    ]
    for severity in SECTIONS:
        group = [f for f in report["findings"] if f["severity"] == severity]
        if not group:
            continue
        lines += ["", f"## {severity} ({len(group)})", ""]
        if severity == "overridden":
            lines += ["| code | detail | by | reason |", "| --- | --- | --- | --- |"]
            lines += [_row(f["code"], f["detail"], f["overridden_by"], f["override_reason"]) for f in group]
        else:
            lines += ["| code | detail |", "| --- | --- |"]
            lines += [_row(f["code"], f["detail"]) for f in group]
    return "\n".join(lines) + "\n"


def _row(*cells: str) -> str:
    return "| " + " | ".join(_escape(cell) for cell in cells) + " |"


def _escape(text: str) -> str:
    return "".join("\\" + ch if ch in ESCAPED else ch for ch in text)


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
    feedback: list[dict] = []
    last = render_summary(gate(list(feedback)))
    yield last
    async for record in records:
        feedback.append(record)
        text = render_summary(gate(list(feedback)))
        if text != last:
            yield BREAK + text
            last = text
