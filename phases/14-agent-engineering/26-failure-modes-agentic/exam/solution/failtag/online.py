"""Tag traces while their steps arrive, and report findings as syslog lines."""
from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from .detectors import (
    WRITE_VERBS,
    SUCCESS_VERBS,
    Rule,
    is_hallucinated,
    is_misused,
    is_write,
    mentions,
    parse_constraint,
    violates,
)
from .trace import TraceStep, references

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


@dataclass
class _Open:
    request: str
    rules: list[Rule]
    steps: int = 0
    failed: set[int] = field(default_factory=set)
    consumers: Counter = field(default_factory=Counter)
    reported: set[str] = field(default_factory=set)


def _sd_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("]", "\\]")


def syslog_line(mode: str, when: float, host: str, params: dict[str, str]) -> str:
    """One RFC 5424 record for a finding, ending in a newline."""
    stamp = dt.datetime.fromtimestamp(when, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    sd = " ".join(f'{name}="{_sd_value(value)}"' for name, value in params.items())
    pri = FACILITY * 8 + SEVERITY[mode]
    return f"<{pri}>1 {stamp}Z {host} failtag - {mode} [{SD_ID} {sd}] {MESSAGES[mode]}\n"


def _step_findings(state: _Open, index: int, step: TraceStep) -> list[str]:
    found = []
    if is_hallucinated(step):
        found.append("hallucinated_action")
    if is_write(step) and not mentions(state.request, WRITE_VERBS):
        found.append("scope_creep")
    if step.kind == "tool_call":
        for ref in references(step) & state.failed:
            state.consumers[ref] += 1
            if state.consumers[ref] == 2:
                found.append("cascading_errors")
        if step.status == "error":
            state.failed.add(index)
    if any(violates(rule, step) for rule in state.rules):
        found.append("context_loss")
    if is_misused(step):
        found.append("tool_misuse")
    return found


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
    open_traces: dict[str, _Open] = {}
    async for event in events:
        if isinstance(event, Start):
            rules = [rule for rule in map(parse_constraint, event.constraints) if rule]
            open_traces[event.tid] = _Open(event.user_request, rules)
            continue
        state = open_traces[event.tid]
        if isinstance(event, Step):
            index = state.steps
            state.steps += 1
            modes = _step_findings(state, index, event.step)
            params = {"tid": event.tid, "step": str(index), "tool": event.step.name}
        else:
            del open_traces[event.tid]
            modes = []
            if (
                mentions(state.request, SUCCESS_VERBS)
                and event.final_success_claim
                and not event.target_state_changed
            ):
                modes.append("success_hallucination")
            params = {"tid": event.tid}
        for mode in modes:
            if mode not in state.reported:
                state.reported.add(mode)
                yield syslog_line(mode, clock(), host, params)
