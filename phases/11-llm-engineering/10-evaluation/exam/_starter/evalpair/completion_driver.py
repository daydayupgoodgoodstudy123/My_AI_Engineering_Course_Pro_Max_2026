"""Given correctly bound async completion driver and local finite JUnit support."""
import asyncio
from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True)
class CompletedCase:
    case_id: str
    category: str
    model_output: str
    reference_output: object
    elapsed_us: int
    judge_passed: object
    error: object=None
@dataclass(frozen=True)
class EvalJob:
    case_id: str
    run: object
async def completed_cases(jobs):
    async def run(job):return await job.run()
    tasks=[asyncio.create_task(run(job)) for job in jobs]
    try:
        for task in asyncio.as_completed(tasks):yield await task
    finally:
        for task in tasks:
            if not task.done():task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
def seconds_text(elapsed_us):return format(Decimal(elapsed_us)/Decimal(1000000),'f')
