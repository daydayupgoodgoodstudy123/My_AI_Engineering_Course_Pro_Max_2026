"""The init run history: one JSON line per run, for the human who has to work out why init
refused to launch."""
from __future__ import annotations

import json
from pathlib import Path

from .probes import STATUSES, Result
from .report import InitReport


class RunHistory:
    """Every init run, appended as one JSON object per line to a file that is never rewritten.

    A run is on disk as soon as append returns, so a second reader (a human, another init
    process) sees it right away, and it comes back exactly as it went in: the float timestamp
    to the last bit, durations as whole milliseconds, details with their quotes and line
    breaks, results in the order the probes are listed.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, report: InitReport) -> None:
        """Add one run at the end of the file.

        A run that cannot have happened is refused with ValueError and nothing is written: a
        result whose status is not pass, warn, fail or skip, or whose duration_ms is not a
        whole number of milliseconds of at least 0 (a stepped clock, or seconds by mistake).
        """
        _check(report)
        line = json.dumps(_encode(report)) + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)

    def runs(self) -> list[InitReport]:
        """Every run on disk now, in the order they were appended. A missing file holds no runs.

        A line that is not a run raises ValueError naming its line number ("line 3"): a history
        that skips what it cannot read hides the run someone is looking for.
        """
        if not self.path.exists():
            return []
        runs = []
        with self.path.open(encoding="utf-8") as f:
            for number, line in enumerate(f, 1):
                try:
                    report = _decode(json.loads(line))
                except (ValueError, KeyError, TypeError) as exc:
                    raise ValueError(f"{self.path} line {number} is not an init run: {exc}") from None
                runs.append(report)
        return runs

    def last_ready(self) -> InitReport | None:
        """The most recent run that let the agent launch (exit_code 0), or None."""
        return next((run for run in reversed(self.runs()) if run.exit_code == 0), None)

    def close(self) -> None:
        """Release anything the history holds open."""


def _check(report: InitReport) -> None:
    for r in report.results:
        if r.status not in STATUSES:
            raise ValueError(f"{r.name}: status must be one of {STATUSES}, got {r.status!r}")
        if not isinstance(r.duration_ms, int) or isinstance(r.duration_ms, bool) or r.duration_ms < 0:
            raise ValueError(f"{r.name}: duration_ms must be whole milliseconds >= 0: {r.duration_ms!r}")


def _encode(report: InitReport) -> dict:
    results = [
        {"name": r.name, "status": r.status, "detail": r.detail, "duration_ms": r.duration_ms}
        for r in report.results
    ]
    return {
        "timestamp": report.timestamp,
        "fingerprint": report.fingerprint,
        "exit_code": report.exit_code,
        "blocking": list(report.blocking),
        "warnings": list(report.warnings),
        "results": results,
    }


def _decode(obj: object) -> InitReport:
    if not isinstance(obj, dict):
        raise ValueError("not a JSON object")
    return InitReport(
        timestamp=obj["timestamp"],
        fingerprint=obj["fingerprint"],
        results=[Result(r["name"], r["status"], r["detail"], r["duration_ms"]) for r in obj["results"]],
        blocking=list(obj["blocking"]),
        warnings=list(obj["warnings"]),
        exit_code=obj["exit_code"],
    )
