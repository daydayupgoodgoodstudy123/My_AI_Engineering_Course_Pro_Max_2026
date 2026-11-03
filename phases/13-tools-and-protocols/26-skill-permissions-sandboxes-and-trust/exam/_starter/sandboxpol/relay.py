"""Relay a sandboxed process's output to the host while it runs.

The host forwards stdout as raw bytes as it arrives, with every injected secret replaced,
within an output limit and a time limit, and then says how the run ended.
"""
from __future__ import annotations

import asyncio
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
        raise NotImplementedError
