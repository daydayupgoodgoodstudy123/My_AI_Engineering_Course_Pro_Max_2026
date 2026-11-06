"""Run the agent's shell commands and record what really happened.

Every command goes through FeedbackRunner.run. Its record carries the exact argv, the redacted
and truncated stdout and stderr, the exit code, how long it took, when it started and the
agent's one-line note, and it reaches the sink before run returns.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from collections.abc import Callable, Sequence
from functools import partial
from typing import Optional

from .record import FeedbackRecord
from .redact import redact
from .truncate import HEAD_LINES, TAIL_LINES, truncate_lines

Truncate = Callable[[str], tuple[str, int]]
Execute = Callable[[list[str], Optional[str], float], subprocess.CompletedProcess]

COMMAND_NOT_FOUND = 127


def run_process(argv: list[str], cwd: str | None, timeout: float) -> subprocess.CompletedProcess[bytes]:
    """Run argv without a shell and capture both streams as bytes.

    Raises subprocess.TimeoutExpired when the command runs out of time (subprocess.run kills it),
    and OSError when it cannot start.
    """
    return subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, check=False)


def new_command_id() -> str:
    return uuid.uuid4().hex[:12]


class JsonlSink:
    """Appends each record to a JSONL file, one line per record."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = path

    def append(self, record: FeedbackRecord) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(record.to_json() + "\n")


class FeedbackRunner:
    def __init__(
        self,
        sink,
        *,
        execute: Execute = run_process,
        truncate: Truncate | None = None,
        new_id: Callable[[], str] = new_command_id,
    ) -> None:
        self.sink = sink
        self.execute = execute
        self.truncate = truncate or partial(truncate_lines, head=HEAD_LINES, tail=TAIL_LINES)
        self.new_id = new_id

    def run(
        self,
        command: Sequence[str],
        *,
        note: str = "",
        cwd: str | None = None,
        timeout_s: float = 30.0,
        parent: str | None = None,
    ) -> FeedbackRecord:
        """Run one command and record it. Whatever happens, the record reaches the sink before run returns.

        - A command that ran to the end keeps its exit code, zero or not.
        - A command that ran out of time has been killed: exit_code is None, error is
          "timeout after <timeout_s>s", and what it printed before that is captured like any
          other output.
        - A command that could not start (no such program, no permission, no such directory)
          has exit_code None and error "<exception class>: <message>".
        - cwd is where the command runs, recorded as given; None is the current directory,
          recorded as its path.
        - parent is the command_id of the attempt this command retries.
        """
        argv = list(command)
        started_at = time.time()
        start = time.monotonic()
        base = dict(
            command_id=self.new_id(),
            parent_command_id=parent,
            command=argv,
            cwd=os.getcwd() if cwd is None else cwd,
            started_at=started_at,
            agent_note=note,
        )
        try:
            done = self.execute(argv, cwd, timeout_s)
        except subprocess.TimeoutExpired as exc:
            record = FeedbackRecord(
                **base,
                stdout_tail=exc.stdout or "",
                stderr_tail=exc.stderr or "",
                exit_code=None,
                duration_ms=_ms_since(start),
                error=f"timeout after {timeout_s}s",
                truncations={"stdout": 0, "stderr": 0},
                redactions={"stdout": 0, "stderr": 0},
            )
        except FileNotFoundError as exc:
            record = FeedbackRecord(
                **base,
                stdout_tail="",
                stderr_tail="",
                exit_code=COMMAND_NOT_FOUND,
                duration_ms=_ms_since(start),
                error=f"{type(exc).__name__}: {exc}",
                truncations={"stdout": 0, "stderr": 0},
                redactions={"stdout": 0, "stderr": 0},
            )
        else:
            out, out_cut, out_hits = self._capture(_decode(done.stdout))
            err, err_cut, err_hits = self._capture(_decode(done.stderr))
            record = FeedbackRecord(
                **base,
                stdout_tail=out,
                stderr_tail=err,
                exit_code=done.returncode,
                duration_ms=_ms_since(start),
                truncations={"stdout": out_cut, "stderr": err_cut},
                redactions={"stdout": out_hits, "stderr": err_hits},
            )
        self.sink.append(record)
        return record

    def _capture(self, text: str) -> tuple[str, int, int]:
        """What a record keeps of one stream: (text, lines cut, secrets replaced).

        No part of a secret may reach the record, not even a secret the cut runs through.
        """
        kept, cut = self.truncate(text)
        clean, hits = redact(kept)
        return clean, cut, hits


def loop_can_advance(record: FeedbackRecord) -> bool:
    """The agent's loop moves on only with feedback: an exit code, zero or not. No exit, no progress."""
    return record.exit_code is not None


def _decode(data: bytes | None) -> str:
    """Captured bytes as text. Bytes that are not UTF-8 become U+FFFD, so binary output still gets a record."""
    return data.decode("utf-8") if data else ""


def _ms_since(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
