"""Follow a command while it runs: its output line by line as it arrives, then its record."""
from __future__ import annotations

import asyncio
import json
from collections import deque
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
    if head < 0 or tail < 0:
        raise ValueError(f"head and tail must not be negative, got head={head}, tail={tail}")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    pipes = {"stdout": process.stdout, "stderr": process.stderr}
    kept = {name: _Kept(head, tail) for name in pipes}
    reading = {name: asyncio.ensure_future(pipe.read(chunk_size)) for name, pipe in pipes.items()}
    timed_out = False
    exit_code: int | None = None
    try:
        while reading:
            done, _ = await asyncio.wait(
                reading.values(),
                timeout=max(0.0, deadline - loop.time()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                timed_out = True
                break
            for name in list(reading):
                task = reading[name]
                if task not in done:
                    continue
                data = task.result()
                if not data:
                    del reading[name]
                    continue
                reading[name] = asyncio.ensure_future(pipes[name].read(chunk_size))
                lines = kept[name].feed(data)
                if lines:
                    yield b"".join(PREFIX[name] + line + b"\n" for line in lines)
        if not timed_out and process.returncode is None:
            remaining = deadline - loop.time()
            if remaining <= 0:
                timed_out = True
            else:
                try:
                    await asyncio.wait_for(process.wait(), remaining)
                except asyncio.TimeoutError:
                    timed_out = True
        if not timed_out:
            exit_code = process.returncode
    finally:
        for task in reading.values():
            task.cancel()
    if timed_out:
        if process.returncode is None:
            process.kill()
        await process.wait()
    last = b""
    for name in pipes:
        line = kept[name].finish()
        if line is not None:
            last += PREFIX[name] + line + b"\n"
    if last:
        yield last
    record = {
        "command": list(command),
        "exit_code": exit_code,
        "error": f"timeout after {timeout_s}s" if timed_out else None,
        "stdout_tail": kept["stdout"].text(),
        "stderr_tail": kept["stderr"].text(),
        "truncations": {name: kept[name].cut for name in pipes},
    }
    yield b"[record] " + json.dumps(record, ensure_ascii=False).encode("utf-8") + b"\n"


class _Kept:
    """What follow() keeps of one pipe: the first lines, the last lines and the line being written."""

    def __init__(self, head: int, tail: int) -> None:
        self.head = head
        self.first: list[bytes] = []
        self.last: deque[bytes] = deque(maxlen=tail)
        self.lines = 0
        self.pending = b""
        self.unfinished = False

    def feed(self, data: bytes) -> list[bytes]:
        """Take one chunk; return the lines it completed."""
        lines = (self.pending + data).split(b"\n")
        self.pending = lines.pop()
        for line in lines:
            self._keep(line)
        return lines

    def finish(self) -> bytes | None:
        """The pipe is done: the line still being written, if any, counts as the last line."""
        if not self.pending:
            return None
        line, self.pending = self.pending, b""
        self._keep(line)
        self.unfinished = True
        return line

    @property
    def cut(self) -> int:
        return self.lines - len(self.first) - len(self.last)

    def text(self) -> str:
        lines = [line.decode("utf-8", errors="replace") for line in self.first]
        if self.cut:
            lines.append(f"...truncated {self.cut} lines...")
        lines.extend(line.decode("utf-8", errors="replace") for line in self.last)
        if not lines:
            return ""
        return "\n".join(lines) + ("" if self.unfinished else "\n")

    def _keep(self, line: bytes) -> None:
        self.lines += 1
        if len(self.first) < self.head:
            self.first.append(line)
        else:
            self.last.append(line)
