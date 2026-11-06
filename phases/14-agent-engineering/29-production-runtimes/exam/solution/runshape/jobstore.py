"""Durable background jobs in SQLite: a crash or restart loses nothing, and every attempt counts."""
from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass

INTERRUPTED = "interrupted"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    run_at_ms INTEGER NOT NULL,
    errors TEXT NOT NULL,
    result TEXT,
    died INTEGER
)
"""

COLUMNS = "job_id, payload, status, attempts, run_at_ms, errors, result"


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
        with self._db:
            self._db.execute(SCHEMA)
        running = self._db.execute(
            "SELECT job_id FROM jobs WHERE status = 'running' ORDER BY seq"
        ).fetchall()
        for (job_id,) in running:
            self.fail(job_id, INTERRUPTED)

    def add(self, payload: str) -> str:
        """Store a new pending job, due now, and return its id."""
        job_id = uuid.uuid4().hex
        with self._db:
            self._db.execute(
                "INSERT INTO jobs (job_id, payload, status, attempts, run_at_ms, errors)"
                " VALUES (?, ?, 'pending', 0, ?, '[]')",
                (job_id, payload, self._clock()),
            )
        return job_id

    def claim(self) -> StoredJob | None:
        """Mark the next due job running and return it, or None when nothing is due."""
        with self._db:
            row = self._db.execute(
                "SELECT job_id FROM jobs WHERE status = 'pending' AND run_at_ms <= ?"
                " ORDER BY run_at_ms, seq LIMIT 1",
                (self._clock(),),
            ).fetchone()
            if row is None:
                return None
            self._db.execute(
                "UPDATE jobs SET status = 'running', attempts = attempts + 1 WHERE job_id = ?", row
            )
        return self.get(row[0])

    def complete(self, job_id: str, result: str) -> StoredJob:
        """Store the result of a running job; the job is done."""
        self._running(job_id)
        with self._db:
            self._db.execute(
                "UPDATE jobs SET status = 'done', result = ? WHERE job_id = ?", (result, job_id)
            )
        return self.get(job_id)

    def fail(self, job_id: str, error: str) -> StoredJob:
        """Record a failed attempt of a running job: back off and retry, or let it die."""
        job = self._running(job_id)
        errors = json.dumps([*job.errors, error])
        with self._db:
            if job.attempts < self.max_attempts:
                run_at = self._clock() + self.backoff_ms * 2 ** (job.attempts - 1)
                self._db.execute(
                    "UPDATE jobs SET status = 'pending', run_at_ms = ?, errors = ? WHERE job_id = ?",
                    (run_at, errors, job_id),
                )
            else:
                (died,) = self._db.execute("SELECT COALESCE(MAX(died), 0) + 1 FROM jobs").fetchone()
                self._db.execute(
                    "UPDATE jobs SET status = 'dead', errors = ?, died = ? WHERE job_id = ?",
                    (errors, died, job_id),
                )
        return self.get(job_id)

    def get(self, job_id: str) -> StoredJob:
        row = self._db.execute(f"SELECT {COLUMNS} FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return _to_job(row)

    def dead_letters(self) -> list[StoredJob]:
        """Dead jobs, in the order they died."""
        rows = self._db.execute(f"SELECT {COLUMNS} FROM jobs WHERE status = 'dead' ORDER BY died")
        return [_to_job(row) for row in rows]

    def close(self) -> None:
        self._db.close()

    def _running(self, job_id: str) -> StoredJob:
        job = self.get(job_id)
        if job.status != "running":
            raise ValueError(f"job {job_id} is {job.status}, not running")
        return job


def _to_job(row: tuple) -> StoredJob:
    job_id, payload, status, attempts, run_at_ms, errors, result = row
    return StoredJob(job_id, payload, status, attempts, run_at_ms, tuple(json.loads(errors)), result)
