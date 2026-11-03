"""Stream repeated-run trigger evals to CI as JUnit XML."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass

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
    raise NotImplementedError
