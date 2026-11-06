"""Run init probes, and keep the prereqs lock that lets a later run skip them."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path

from .probes import Probe, Result

LOCK_TTL_S = 24 * 60 * 60


async def _timed(probe: Probe) -> Result:
    """Run one probe and time it.

    The duration comes from the monotonic clock, so a wall-clock step (NTP, a laptop waking
    up) never makes it negative or huge. A probe that raises does not take init down: it
    becomes a fail result for that probe, with "<ExceptionType>: <message>" as its detail,
    timed like any other. A pass that runs over the probe's budget_s becomes a warn, with
    " (slow: <ms>ms > <budget>ms)" added to its detail; other statuses are left as they are.
    A slow fail stays a fail with its own detail: turned into a warn, it would no longer stop
    the launch.
    """
    started = time.time()
    try:
        status, detail = await probe.check()
    except Exception as exc:
        status, detail = "fail", f"{type(exc).__name__}: {exc}"
    duration_ms = int((time.time() - started) * 1000)
    if duration_ms > probe.budget_s * 1000:
        status = "warn"
        detail = f"{detail} (slow: {duration_ms}ms > {int(probe.budget_s * 1000)}ms)"
    return Result(probe.name, status, detail, duration_ms)


async def run_probes(probes: list[Probe]) -> list[Result]:
    """Run probes that do not depend on each other, and return their results in the order
    the probes are listed.

    They all run at the same time, so the run takes about as long as the slowest probe, not
    the sum of them. (run_init in plan.py adds severities and needs on top.)
    """
    return list(await asyncio.gather(*(_timed(probe) for probe in probes)))


def fingerprint(manifest: str, probes: list[Probe]) -> str:
    """What a lock is valid for: the dependency manifest's text and the set of probe names.

    Editing the manifest, or adding, removing or renaming a probe, changes the fingerprint.
    The order the probes are listed in does not, and neither does which process built them.
    The manifest and the sorted names are hashed once each: init checks the lock at every
    start, and a monorepo can have a probe for each of thousands of locked packages.
    """
    names: list[str] = []
    digest = hashlib.sha256(manifest.encode())
    for name in sorted(probe.name for probe in probes):
        names.append(name)
        digest = hashlib.sha256(manifest.encode() + b"\0" + json.dumps(names).encode())
    return digest.hexdigest()[:16]


def write_lock(lock_path: str | Path, manifest: str, probes: list[Probe], now: float) -> None:
    """Record that a run at wall-clock time `now` was ready to launch."""
    Path(lock_path).write_text(
        json.dumps({"fingerprint": fingerprint(manifest, probes), "written_at": now}) + "\n",
        encoding="utf-8",
    )


def lock_is_fresh(lock_path: str | Path, manifest: str, probes: list[Probe], now: float) -> bool:
    """Whether the lock can stand in for running the probes at wall-clock time `now`.

    It can while its fingerprint matches and its age is at least 0 and under LOCK_TTL_S.
    A missing, unreadable or malformed lock is not fresh, and neither is one stamped in the
    future (a clock that was set back, or a hand-edited file): its age cannot be trusted.
    """
    path = Path(lock_path)
    if not path.exists():
        return False
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(lock, dict) or lock.get("fingerprint") != fingerprint(manifest, probes):
        return False
    written_at = lock.get("written_at")
    if not isinstance(written_at, (int, float)) or isinstance(written_at, bool):
        return False
    age = now - written_at
    return age < LOCK_TTL_S
