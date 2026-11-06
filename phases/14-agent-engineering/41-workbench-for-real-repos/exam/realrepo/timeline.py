"""A live timeline of the runs: when each one reaches each milestone, streamed as CSV."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .artifacts import Contract

MILESTONES = ("first_meaningful_edit", "tests_run", "acceptance_met")


async def milestones(
    runs: dict[str, AsyncIterator[dict]], contract: Contract
) -> AsyncIterator[str]:
    """Stream when each run reaches each milestone, as CSV, while the runs are still going.

    runs maps a pipeline name to its run's events, in the order they happen. Every event has
    t_ms, the milliseconds since that run started, and a kind:
      {"kind": "edit", "path": ..., "before": text, "after": text}   the run wrote a file
      {"kind": "command", "record": FeedbackRecord}                   a command finished
    Events of other kinds ("read", "claim", ...) reach no milestone.

    The milestones, in MILESTONES order:
      first_meaningful_edit  the first edit that changes code: to a .py file the contract
                             allows, changing more than comments, blank lines and whitespace
      tests_run              the first time the records so far show a test that ran
                             (realrepo.outcomes.latest_results)
      acceptance_met         the first time the records so far meet the contract's acceptance
                             (realrepo.outcomes.acceptance_met)

    The first string is the header pipeline,milestone,t_ms. After it, as soon as an event takes
    its run to a milestone for the first time, one record for each milestone it reaches (in
    MILESTONES order): the pipeline, the milestone and that event's t_ms. When a run's events
    end, one record for each milestone it never reached, in MILESTONES order, with an empty t_ms.
    The runs are read at the same time: a run that is waiting holds back none of the others.
    Each yielded string is one csv.writer record with its line ending.
    """
    raise NotImplementedError
