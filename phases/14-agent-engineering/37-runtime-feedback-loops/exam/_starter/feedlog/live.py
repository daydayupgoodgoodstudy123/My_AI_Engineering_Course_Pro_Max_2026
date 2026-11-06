"""Follow a command while it runs: its output line by line as it arrives, then its record."""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from .truncate import HEAD_LINES, TAIL_LINES

PREFIX = {"stdout": b"[stdout] ", "stderr": b"[stderr] "}


class Pipe(Protocol):
    async def read(self, n: int = -1) -> bytes:
        """Up to n bytes as soon as there are some; b"" once the pipe is closed and drained."""


class Process(Protocol):
    """What follow() needs of a running process. asyncio.subprocess.Process has all of it."""

    stdout: Pipe
    stderr: Pipe
    returncode: int | None

    async def wait(self) -> int: ...

    def kill(self) -> None: ...


async def follow(
    process: Process,
    command: Sequence[str],
    *,
    head: int = HEAD_LINES,
    tail: int = TAIL_LINES,
    timeout_s: float = 30.0,
    chunk_size: int = 65536,
) -> AsyncIterator[bytes]:
    """Relay a running command's output line by line, then yield its record.

    - Read stdout and stderr at the same time, as the command writes them. A command that fills
      a pipe nobody reads stops until someone does.
    - After each chunk read, yield the lines that chunk completed, as one bytes object: each line
      as b"[stdout] " or b"[stderr] ", its bytes exactly as written, and b"\\n". A chunk that
      completes no line yields nothing. A line ends at b"\\n"; the start of a line waits, on its
      own pipe, for the rest of it.
    - Memory does not grow with the output: per pipe, keep only the first head lines, the last
      tail lines and the line being written.
    - The whole run gets timeout_s seconds, waiting for the exit included. When they are up, kill
      the process and stop reading.
    - At the end, an unfinished last line of each pipe goes out like the others, then the record:
      b"[record] ", one line of JSON, b"\\n". Its keys are command, exit_code, error,
      stdout_tail, stderr_tail and truncations. Each tail is laid out the way
      truncate_lines(output, head, tail) lays out that pipe's output, decoded as UTF-8 with
      U+FFFD for bytes that are not; truncations counts, per pipe, the lines left out. A command
      that ran out of time has exit_code None and error "timeout after <timeout_s>s"; otherwise
      error is None.
    - Nothing here is redacted. This is the agent's live view, and it is not written anywhere.
    """
    raise NotImplementedError
