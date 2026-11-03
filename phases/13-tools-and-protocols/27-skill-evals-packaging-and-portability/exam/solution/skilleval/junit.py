"""Stream repeated-run trigger evals to CI as JUnit XML."""
from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from xml.sax.saxutils import quoteattr

from .cases import TriggerCase, check_cases
from .metrics import run_matched


@dataclass(frozen=True)
class Reply:
    """What the target runtime answered on one run: the skill it invoked (None: it abstained),
    the latency in milliseconds, and its raw trace."""

    predicted_skill: str | None
    latency_ms: float
    trace: str


Router = Callable[[str, int], Awaitable[Reply]]


async def junit_stream(
    cases: Sequence[TriggerCase],
    router: Router,
    skill: str,
    runs: int,
    concurrency: int,
) -> AsyncIterator[str]:
    """Run every case `runs` times through router(prompt, run) and stream the results as JUnit XML.

    At most `concurrency` router calls are in flight at once, across all cases. The chunks are:

    1. <testsuite name="{skill}" tests="{number of cases}">, before any run has finished;
    2. one complete <testcase classname="{category}" name="{case_id}" time="{seconds}"> element
       per case, in declared order, each as soon as that case and every case before it are done.
       time is the case's total router latency, in seconds. When any run did not match, the
       testcase holds <failure message="{matched}/{runs} runs matched: {prompt}"
       type="trigger-mismatch">, whose text has one line "run {i}: {trace}" per run;
    3. <properties> with one <property name=... value=.../> each for failures (failed cases),
       runs and matched (both counted over every run), then </testsuite>.

    Every attribute value and text reaches an XML parser exactly as given. runs or concurrency
    below 1 raises ValueError before any call.
    """
    check_cases(cases, skill)
    if runs < 1 or concurrency < 1:
        raise ValueError("runs and concurrency must be at least 1")
    limit = asyncio.Semaphore(concurrency)

    async def one(case: TriggerCase, run: int) -> Reply:
        async with limit:
            return await router(case.prompt, run)

    async def every_run(case: TriggerCase) -> list[Reply]:
        return list(await asyncio.gather(*(one(case, run) for run in range(runs))))

    pending = [asyncio.ensure_future(every_run(case)) for case in cases]
    try:
        yield f'<testsuite name={quoteattr(skill)} tests="{len(cases)}">'
        failures = matched_runs = 0
        for case, task in zip(cases, pending):
            replies = await task
            matched = sum(run_matched(case, reply.predicted_skill, skill) for reply in replies)
            matched_runs += matched
            failures += matched < runs
            yield _testcase(case, replies, matched)
        properties = ET.Element("properties")
        for name, value in (("failures", failures), ("runs", runs * len(cases)), ("matched", matched_runs)):
            ET.SubElement(properties, "property", name=name, value=str(value))
        yield ET.tostring(properties, encoding="unicode") + "</testsuite>"
    finally:
        for task in pending:
            task.cancel()


def _testcase(case: TriggerCase, replies: list[Reply], matched: int) -> str:
    seconds = sum(reply.latency_ms for reply in replies) / 1000
    element = ET.Element("testcase", classname=case.category, name=case.case_id, time=repr(seconds))
    if matched < len(replies):
        failure = ET.SubElement(
            element,
            "failure",
            message=f"{matched}/{len(replies)} runs matched: {case.prompt}",
            type="trigger-mismatch",
        )
        failure.text = "\n".join(f"run {index}: {reply.trace}" for index, reply in enumerate(replies))
    return ET.tostring(element, encoding="unicode")
