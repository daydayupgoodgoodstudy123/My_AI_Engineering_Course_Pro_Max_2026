"""Tag traces while their steps arrive, and report findings as syslog lines."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from .trace import TraceStep

FACILITY = 16  # local0
SEVERITY = {
    "hallucinated_action": 3,
    "scope_creep": 4,
    "cascading_errors": 2,
    "context_loss": 3,
    "tool_misuse": 4,
    "success_hallucination": 3,
}
MESSAGES = {
    "hallucinated_action": "agent called a tool that does not exist",
    "scope_creep": "agent wrote although the request asked for no write",
    "cascading_errors": "a failed call's result was used downstream",
    "context_loss": "a tool call broke a do-not constraint",
    "tool_misuse": "a tool was called with the wrong arguments",
    "success_hallucination": "agent claimed success but the target state did not change",
}
SD_ID = "failtag@32473"


@dataclass(frozen=True)
class Start:
    tid: str
    user_request: str
    constraints: list[str]


@dataclass(frozen=True)
class Step:
    tid: str
    step: TraceStep


@dataclass(frozen=True)
class End:
    tid: str
    final_success_claim: bool
    target_state_changed: bool


async def tag_online(
    events: AsyncIterator[Start | Step | End],
    clock: Callable[[], float],
    host: str = "-",
) -> AsyncIterator[str]:
    """Tag traces while their events arrive, and yield one syslog line per finding.

    Events of several traces may interleave; each trace opens with Start and closes with
    End. A finding is yielded as soon as the event that proves it arrives:
    hallucinated_action, scope_creep, context_loss and tool_misuse at the offending step,
    cascading_errors at the second tool call that uses the same failed call's result, and
    success_hallucination at End. Each mode is reported at most once per trace; findings
    proved by the same event come in DETECTORS order.

    Each line is an RFC 5424 record followed by "\\n":

        <PRI>1 TIMESTAMP HOST failtag - MODE [failtag@32473 tid="..." step="N" tool="..."] MESSAGE

    PRI is FACILITY * 8 + SEVERITY[mode]. TIMESTAMP is clock() at that moment, in UTC
    with milliseconds and a Z, e.g. 2026-11-02T08:30:00.250Z. step is the 0-based index of
    the step within its trace and tool is that step's name; findings at End carry only tid.
    In param values, '"', '\\' and ']' are escaped with a backslash (RFC 5424, 6.3.3):
    escape every '\\' first, then '"' and ']'. MESSAGE is MESSAGES[mode].
    """
    raise NotImplementedError
