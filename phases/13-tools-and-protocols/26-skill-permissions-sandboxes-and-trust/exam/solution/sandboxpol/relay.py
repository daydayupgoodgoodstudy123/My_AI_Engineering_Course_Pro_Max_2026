"""Relay a sandboxed process's output to the host while it runs.

The host forwards stdout as raw bytes as it arrives, with every injected secret replaced,
within an output limit and a time limit, and then says how the run ended.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Protocol

PLACEHOLDER = b"[REDACTED]"
TRUNCATED = b"\n[output truncated]\n"

EXIT_INVALID_INPUT = 2
EXIT_POLICY_DENIED = 3


class SandboxProcess(Protocol):
    def stdout(self) -> AsyncIterator[bytes]:
        """The process's stdout, chunk by chunk, until it exits."""

    async def wait(self) -> int:
        """The exit code, once the process has exited (negative when killed by a signal)."""

    def kill(self) -> None:
        """Stop the process now."""


@dataclass(frozen=True)
class RelayReport:
    status: str  # "ok", "invalid-input", "policy-denied", "execution-failed" or "timed-out"
    exit_code: int
    truncated: bool


class OutputRelay:
    """Forwards one run's stdout. After relay() finishes, report says how the run ended."""

    def __init__(self, secrets: Iterable[str], limit: int, timeout: float) -> None:
        self.secrets = [secret.encode("utf-8") for secret in secrets if secret]
        self.limit = limit
        self.timeout = timeout
        self.report: RelayReport | None = None

    async def relay(self, process: SandboxProcess) -> AsyncIterator[bytes]:
        """Forward the process's stdout as it arrives, as raw bytes.

        - Every occurrence of a secret becomes PLACEHOLDER, also when the chunks split it;
          where several secrets match at the same place, the longest one is replaced.
          Only the tail that a later chunk could still change waits: fewer bytes than the
          longest secret, plus the start of a UTF-8 character whose other bytes have not
          arrived. Everything before that tail is forwarded as soon as it arrives.
        - At most limit bytes of redacted output are forwarded; TRUNCATED does not count.
          When the output goes past the limit, the relay forwards what fits without
          splitting a UTF-8 character, then TRUNCATED, and nothing more. It keeps reading
          until the process exits.
        - The whole run gets timeout seconds. When they are up, the relay kills the process,
          forwards what the process wrote before the deadline (redacted, within the limit)
          and stops.
        - Once the stream has ended, self.report holds the exit code from process.wait(),
          whether the output was truncated, and the status: exit code 0 is "ok",
          EXIT_INVALID_INPUT is "invalid-input", EXIT_POLICY_DENIED is "policy-denied", any
          other exit code is "execution-failed", and a run that hit the timeout is "timed-out"
          whatever its exit code.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout
        redactor = _Redactor(self.secrets)
        limiter = _Limiter(self.limit)
        chunks = process.stdout().__aiter__()
        timed_out = False
        finished = False
        try:
            while True:
                remaining = deadline - loop.time()
                try:
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    chunk = await asyncio.wait_for(chunks.__anext__(), remaining)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    timed_out = True
                    process.kill()
                    break
                piece = limiter.take(redactor.feed(chunk))
                if piece:
                    yield piece
            piece = limiter.take(redactor.flush())
            if piece:
                yield piece
            exit_code = await process.wait()
            finished = True
        finally:
            if not finished:
                process.kill()
        if timed_out:
            status = "timed-out"
        elif exit_code == 0:
            status = "ok"
        elif exit_code == EXIT_INVALID_INPUT:
            status = "invalid-input"
        elif exit_code == EXIT_POLICY_DENIED:
            status = "policy-denied"
        else:
            status = "execution-failed"
        self.report = RelayReport(status, exit_code, limiter.truncated)


class _Redactor:
    """Replaces secrets in a byte stream, holding back only what a later chunk may complete."""

    def __init__(self, secrets: list[bytes]) -> None:
        ordered = sorted(set(secrets), key=len, reverse=True)
        self._pattern = re.compile(b"|".join(map(re.escape, ordered))) if ordered else None
        self._hold = max(map(len, ordered), default=1) - 1
        self._pending = b""

    def feed(self, chunk: bytes) -> bytes:
        self._pending += chunk
        return self._release(len(self._pending) - self._hold, final=False)

    def flush(self) -> bytes:
        return self._release(len(self._pending), final=True)

    def _release(self, boundary: int, final: bool) -> bytes:
        data = self._pending
        out = bytearray()
        pos = 0
        if self._pattern is not None:
            for match in self._pattern.finditer(data):
                if match.start() >= boundary:
                    break
                out += data[pos : match.start()]
                out += PLACEHOLDER
                pos = match.end()
        end = max(pos, boundary)
        if not final:
            end -= _partial_character(data[pos:end])
        out += data[pos:end]
        self._pending = data[end:]
        return bytes(out)


class _Limiter:
    def __init__(self, limit: int) -> None:
        self._room = limit
        self.truncated = False

    def take(self, data: bytes) -> bytes:
        if self.truncated or not data:
            return b""
        if len(data) <= self._room:
            self._room -= len(data)
            return data
        cut = self._room
        while cut > 0 and data[cut] & 0xC0 == 0x80:
            cut -= 1
        self.truncated = True
        self._room = 0
        return data[:cut] + TRUNCATED


def _partial_character(data: bytes) -> int:
    """How many bytes at the end of data begin a UTF-8 character whose other bytes are missing."""
    for back in range(1, min(4, len(data)) + 1):
        byte = data[-back]
        if byte & 0xC0 == 0x80:
            continue
        if byte & 0xE0 == 0xC0:
            need = 2
        elif byte & 0xF0 == 0xE0:
            need = 3
        elif byte & 0xF8 == 0xF0:
            need = 4
        else:
            need = 1
        return back if need > back else 0
    return 0
