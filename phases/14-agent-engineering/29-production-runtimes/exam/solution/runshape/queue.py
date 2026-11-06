"""Background jobs: a queue, a pool of async workers, retries and a dead-letter queue."""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .agent import answer


@dataclass
class Job:
    job_id: str
    payload: str
    attempts: int = 0
    error: str | None = None  # why the job is in the dead-letter queue: the error of its last attempt


class DeadLettered(Exception):
    """QueueRuntime.result raises this for a job that used up its attempts."""

    def __init__(self, job_id: str, error: str) -> None:
        super().__init__(job_id, error)
        self.job_id = job_id
        self.error = error


def never_fail(job: Job) -> str | None:
    return None


class QueueRuntime:
    """Jobs enter a queue and worker tasks pick them up, oldest first.

    Each attempt asks fail_policy(job) once how it ends (the fault-injection hook used to
    simulate flaky jobs): with the error it fails with, or None when it does not fail. An
    attempt that does not fail runs the agent on the payload. A failed job goes to the back
    of the queue until it has had max_attempts attempts in total; then it moves to the
    dead-letter queue (dlq), with the error of its last attempt. log records (job_id,
    "done", "retry" or "dead") for every attempt, in order.

    result(job_id) waits for the job's answer. A dead-lettered job does not vanish for the
    caller: result() raises DeadLettered(job_id, error) as soon as the job is in the
    dead-letter queue, to callers that were already waiting and to callers that ask later.

    An idle worker sleeps until enqueue() gives it work.
    """

    def __init__(
        self,
        agent: Callable[[str], str] = answer,
        fail_policy: Callable[[Job], str | None] = never_fail,
        max_attempts: int = 3,
    ) -> None:
        self.agent = agent
        self.fail_policy = fail_policy
        self.max_attempts = max_attempts
        self.max_retries = max_attempts - 1
        self.queue: deque[Job] = deque()
        self.dlq: list[Job] = []
        self.log: list[tuple[str, str]] = []
        self._answers: dict[str, str] = {}
        self._dead: dict[str, Job] = {}
        self._waiters: dict[str, list[asyncio.Future]] = {}
        self._count = 0
        self._stopping = False
        self._wakeup = asyncio.Event()

    def enqueue(self, payload: str) -> str:
        """Add a job and return its id: j001, j002, ..."""
        self._count += 1
        job = Job(f"j{self._count:03d}", payload)
        self.queue.append(job)
        self._wakeup.set()
        return job.job_id

    async def result(self, job_id: str) -> str:
        """Wait for a job's answer. A job that ended in the dead-letter queue raises DeadLettered."""
        if job_id not in self._answers and job_id not in self._dead:
            waiter = asyncio.get_running_loop().create_future()
            self._waiters.setdefault(job_id, []).append(waiter)
            await waiter
        if job_id in self._dead:
            raise DeadLettered(job_id, self._dead[job_id].error)
        return self._answers[job_id]

    async def serve(self, workers: int = 1) -> None:
        """Run `workers` worker tasks until stop() is called."""
        self._stopping = False
        await asyncio.gather(*(self._work() for _ in range(workers)))

    def stop(self) -> None:
        """Make every worker exit once it is between jobs. Jobs still queued stay queued."""
        self._stopping = True
        self._wakeup.set()

    async def _work(self) -> None:
        while not self._stopping:
            if not self.queue:
                self._wakeup.clear()
                await self._wakeup.wait()
                continue
            self._attempt(self.queue.popleft())

    def _attempt(self, job: Job) -> None:
        job.attempts += 1
        error = self.fail_policy(job)
        if error is not None and job.attempts <= self.max_retries:
            self.queue.append(job)
            self.log.append((job.job_id, "retry"))
            return
        if error is not None:
            job.error = error
            self.dlq.append(job)
            self.log.append((job.job_id, "dead"))
            self._dead[job.job_id] = job
            self._wake_waiters(job.job_id)
            return
        self._answers[job.job_id] = self.agent(job.payload)
        self.log.append((job.job_id, "done"))
        self._wake_waiters(job.job_id)

    def _wake_waiters(self, job_id: str) -> None:
        for waiter in self._waiters.pop(job_id, []):
            if not waiter.done():
                waiter.set_result(None)
