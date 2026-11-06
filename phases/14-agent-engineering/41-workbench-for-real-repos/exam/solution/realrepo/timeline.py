"""A live timeline of the runs: when each one reaches each milestone, streamed as CSV."""
from __future__ import annotations

import asyncio
import csv
import io
import tokenize
from collections.abc import AsyncIterator

from .artifacts import Contract, FeedbackRecord
from .outcomes import acceptance_met, latest_results

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
    queue: asyncio.Queue = asyncio.Queue()
    end = object()

    async def pump(pipeline: str, events: AsyncIterator[dict]) -> None:
        try:
            async for event in events:
                await queue.put((pipeline, event))
        except Exception as exc:  # handed to the reader, which raises it
            await queue.put((pipeline, exc))
        else:
            await queue.put((pipeline, end))

    progress = {pipeline: _Progress(contract) for pipeline in runs}
    tasks = [asyncio.create_task(pump(pipeline, events)) for pipeline, events in runs.items()]
    try:
        yield _record("pipeline", "milestone", "t_ms")
        running = len(tasks)
        while running:
            pipeline, event = await queue.get()
            if isinstance(event, Exception):
                raise event
            if event is end:
                running -= 1
                for milestone in MILESTONES:
                    if milestone not in progress[pipeline].reached:
                        yield _record(pipeline, milestone, "")
                continue
            for milestone in progress[pipeline].advance(event):
                yield _record(pipeline, milestone, event["t_ms"])
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class _Progress:
    """One run's records so far, and the milestones it has reached."""

    def __init__(self, contract: Contract) -> None:
        self.contract = contract
        self.records: list[FeedbackRecord] = []
        self.reached: set[str] = set()

    def advance(self, event: dict) -> list[str]:
        new = []
        kind = event.get("kind")
        if kind == "edit":
            if "first_meaningful_edit" not in self.reached and _meaningful(event, self.contract):
                new.append("first_meaningful_edit")
        elif kind == "command":
            self.records.append(event["record"])
            if "tests_run" not in self.reached and latest_results(self.records):
                new.append("tests_run")
            if "acceptance_met" not in self.reached and acceptance_met(
                self.records, self.contract.acceptance
            ):
                new.append("acceptance_met")
        self.reached.update(new)
        return new


def _meaningful(event: dict, contract: Contract) -> bool:
    path = event["path"]
    if path not in contract.allowed or not path.endswith(".py"):
        return False
    return _code(event["before"]) != _code(event["after"])


_LAYOUT = {tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}


def _code(text: str) -> list[tuple[int, str]] | str:
    """The file's tokens without comments and blank lines, line breaks and indents by kind only.

    Text that does not tokenize is compared as it is.
    """
    try:
        return [
            (tok.type, "" if tok.type in _LAYOUT else tok.string)
            for tok in tokenize.generate_tokens(io.StringIO(text).readline)
            if tok.type not in (tokenize.COMMENT, tokenize.NL)
        ]
    except (tokenize.TokenError, SyntaxError):
        return text


def _record(*fields: object) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(fields)
    return out.getvalue()
