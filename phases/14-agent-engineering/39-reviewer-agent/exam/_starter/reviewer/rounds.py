"""Builder and reviewer turns, alternating until the reviewer passes the work.

The reviewer reads the builder's work and writes a report; it does not patch the diff. If the
report says "fix this", the next builder turn does the fix.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

from .rubric import ReviewReport

Build = Callable[[int, dict[str, str], "ReviewReport | None"], Awaitable[None]]
Review = Callable[[int, Mapping[str, str]], Awaitable[ReviewReport]]


async def build_review_rounds(
    workspace: dict[str, str],
    build: Build,
    review: Review,
    max_rounds: int = 3,
) -> AsyncIterator[str]:
    """Alternate builder and reviewer turns, and stream one CSV record per round.

    Round n awaits build(n, workspace, last_report): the builder edits workspace (path -> text)
    in place, and last_report is the previous round's report (None in round 1). When the
    builder's turn returns, the reviewer gets a read-only snapshot of the workspace as it is at
    that moment: writes that land later (a hook the builder left running) are not in it, and
    writing to the snapshot raises TypeError. Then review(n, snapshot) gives the round's report.

    After a soft_fail the next round starts, and its builder gets that report. A pass ends the
    loop. A hard_fail halts the loop for a human, and so does a round max_rounds that does not
    pass.

    The stream is CSV as csv.writer writes it, one record per string: first the header
    round,changed,total,verdict,next, then one record per round, sent as soon as that round's
    report is in, before the next builder turn starts. changed lists the paths whose text
    differs between this round's snapshot and the previous one (round 1: the workspace before
    the first builder turn), added and deleted paths included, sorted and joined with ";".
    next is "build" (another builder turn follows), "done" (pass) or "human".
    """
    raise NotImplementedError
