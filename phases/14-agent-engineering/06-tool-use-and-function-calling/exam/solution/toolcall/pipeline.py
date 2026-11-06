"""Run an eval suite concurrently and report it as TAP while the cases finish."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from .cases import Call, Case
from .scoring import Verdict, grade, summarize

Model = Callable[[Case], Awaitable[list[Call]]]


async def run_suite(cases: list[Case], model: Model, concurrency: int = 4) -> AsyncIterator[str]:
    """Ask the model about every case, at most `concurrency` at a time, and grade each answer.

    A case starts as soon as a slot is free, in the order of `cases`. Each case gets one TAP
    line the moment it is graded, numbered from 1 in the order the lines come out:

        ok 3 - <case id> # <category>
        not ok 4 - <case id> # <category>: <verdict reason>

    A model call or a grading that raises makes that case "not ok" with the reason
    "error: <ExceptionType>: <message>", and the case counts as wrong; the other cases carry on.
    A reason that spans several lines is joined into one with spaces. After the last case
    comes "# score <total>", Report.total to four decimals ("-" when there are no cases), then
    the plan "1..N". Every line ends with "\\n". A reader that stops early (aclose) cancels the
    cases still running before aclose returns. A concurrency below 1 raises ValueError.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    slots = asyncio.Semaphore(concurrency)
    graded: asyncio.Queue[Verdict] = asyncio.Queue()

    async def run_one(case: Case) -> None:
        async with slots:
            try:
                verdict = grade(case, await model(case))
            except Exception as e:
                reason = f"error: {type(e).__name__}: {e}"
                verdict = Verdict(case.case_id, case.category, False, reason)
        graded.put_nowait(verdict)

    tasks = [asyncio.create_task(run_one(case)) for case in cases]
    verdicts: list[Verdict] = []
    try:
        for number in range(1, len(cases) + 1):
            verdict = await graded.get()
            verdicts.append(verdict)
            yield _tap_line(number, verdict)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    total = summarize(verdicts).total
    yield f"# score {'-' if total is None else f'{total:.4f}'}\n"
    yield f"1..{len(cases)}\n"


def _tap_line(number: int, verdict: Verdict) -> str:
    if verdict.correct:
        return f"ok {number} - {verdict.case_id} # {verdict.category}\n"
    reason = " ".join(verdict.reason.splitlines())
    return f"not ok {number} - {verdict.case_id} # {verdict.category}: {reason}\n"
