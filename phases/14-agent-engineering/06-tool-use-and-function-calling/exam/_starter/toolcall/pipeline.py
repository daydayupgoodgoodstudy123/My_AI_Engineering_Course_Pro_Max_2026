"""Run an eval suite concurrently and report it as TAP while the cases finish."""
from __future__ import annotations

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
    raise NotImplementedError
