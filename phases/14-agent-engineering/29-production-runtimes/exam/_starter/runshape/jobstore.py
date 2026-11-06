"""Durable background jobs in SQLite: a crash or restart loses nothing, and every attempt counts."""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class StoredJob:
    job_id: str
    payload: str
    status: str  # "pending", "running", "done" or "dead"
    attempts: int
    run_at_ms: int  # when the job is (or was last) due
    errors: tuple[str, ...]  # the error of every failed attempt, oldest first
    result: str | None


class JobStore:
    """Background jobs kept in SQLite, so a crash or a restart loses nothing.

    clock() returns the current time in integer milliseconds. add() makes a pending job,
    due now. claim() hands out the pending job that is due (run_at_ms <= now) with the
    earliest run_at_ms, ties in the order the jobs were added; it marks the job running
    and counts the attempt. complete() stores the agent's result.

    fail() records the attempt's error. While the job has had fewer than max_attempts
    attempts it is pending again, due backoff_ms * 2 ** (attempts - 1) after now; after
    the last attempt it is dead and keeps its run_at_ms. dead_letters() lists dead jobs in
    the order they died. complete() and fail() only accept a running job (ValueError);
    an unknown id raises KeyError.

    One process uses a store at a time. Opening it recovers the jobs a previous process
    left running: each one fails with the error "interrupted", exactly as if fail() had
    been called when the store was opened.
    """

    def __init__(
        self, path: str, clock: Callable[[], int], max_attempts: int = 3, backoff_ms: int = 1000
    ) -> None:
        self._db = sqlite3.connect(path)
        self._clock = clock
        self.max_attempts = max_attempts
        self.backoff_ms = backoff_ms
        # TODO: create the schema, then recover the jobs a previous process left running

    def add(self, payload: str) -> str:
        """Store a new pending job, due now, and return its id."""
        raise NotImplementedError

    def claim(self) -> StoredJob | None:
        """Mark the next due job running and return it, or None when nothing is due."""
        raise NotImplementedError

    def complete(self, job_id: str, result: str) -> StoredJob:
        """Store the result of a running job; the job is done."""
        raise NotImplementedError

    def fail(self, job_id: str, error: str) -> StoredJob:
        """Record a failed attempt of a running job: back off and retry, or let it die."""
        raise NotImplementedError

    def get(self, job_id: str) -> StoredJob:
        raise NotImplementedError

    def dead_letters(self) -> list[StoredJob]:
        """Dead jobs, in the order they died."""
        raise NotImplementedError

    def close(self) -> None:
        self._db.close()
