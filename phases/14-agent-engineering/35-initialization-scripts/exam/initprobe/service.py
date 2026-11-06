"""Glue the pre-task hook calls: the lock, the probes, the report file and the history."""
from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from .history import RunHistory
from .plan import ProbeConfigError, run_init
from .probes import Probe
from .report import InitReport
from .runner import lock_is_fresh, write_lock
from .tap import stream_tap


class InitService:
    """The lesson's init_agent.py, for one workbench.

    run() trusts a fresh prereqs.lock and returns None without running anything. Otherwise it
    runs the probes (run_init), writes init_report.json, appends the run to the history, and
    keeps the lock in step with the result: a ready run writes a new lock and any other run
    removes the old one, so the next plain run cannot paper over a failure.
    """

    def __init__(
        self,
        probes: list[Probe],
        manifest: str,
        workdir: str | Path,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.probes = list(probes)
        self.manifest = manifest
        self.clock = clock
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.workdir / "prereqs.lock"
        self.report_path = self.workdir / "init_report.json"
        self.history = RunHistory(self.workdir / "init_history.jsonl")

    def run(self, use_lock: bool = True) -> InitReport | None:
        now = self.clock()
        if use_lock and lock_is_fresh(self.lock_path, self.manifest, self.probes, now):
            return None
        report = asyncio.run(run_init(self.probes, self.manifest, now))
        self.report_path.write_text(report.to_json(), encoding="utf-8")
        self.history.append(report)
        if report.exit_code == 0:
            write_lock(self.lock_path, self.manifest, self.probes, now)
        else:
            self.lock_path.unlink(missing_ok=True)
        return report

    def hook(self, use_lock: bool = True) -> int:
        """Run init for a pre-task hook and return its exit code: 0 launch, 1 refuse, 2 broken."""
        try:
            report = self.run(use_lock)
        except ProbeConfigError as exc:
            print(f"init cannot run: {exc}", file=sys.stderr)
            return 2
        if report is None:
            print("prereqs.lock fresh; skipping probes")
            return 0
        width = max((len(r.name) for r in report.results), default=0)
        for r in report.results:
            print(f"  {r.name:<{width}}  {r.status:>4}  {r.duration_ms:>4}ms  {r.detail}")
        if report.exit_code:
            print(f"init failed; refuse to launch agent: {', '.join(report.blocking)}", file=sys.stderr)
        return report.exit_code

    def stream(self) -> AsyncIterator[str]:
        """The same run as TAP, for a CI log; see stream_tap."""
        return stream_tap(self.probes)

    def close(self) -> None:
        self.history.close()
