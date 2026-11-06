"""What a probe is, and what it found."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

STATUSES = ("pass", "warn", "fail", "skip")
SEVERITIES = ("block", "warn", "info")
PROBE_BUDGET_S = 3.0  # a probe slower than this in a dry run is a workbench smell


@dataclass(frozen=True)
class Probe:
    """One deterministic check that init runs before the agent starts.

    check() looks at the workbench and returns (status, detail), status being pass, warn or
    fail. severity says what a failure means for the launch: block refuses it, warn and info
    let the agent start. needs names the probes that must pass (or warn) before this one can
    run at all. budget_s is how long the probe may take before it counts as slow.
    """

    name: str
    check: Callable[[], Awaitable[tuple[str, str]]]
    severity: str = "block"
    needs: tuple[str, ...] = ()
    budget_s: float = PROBE_BUDGET_S


@dataclass
class Result:
    """What one probe found. status is pass, warn, fail, or skip for a probe that never ran."""

    name: str
    status: str
    detail: str
    duration_ms: int = 0
