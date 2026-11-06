"""The init report: what the agent reads at startup instead of probing again."""
from __future__ import annotations

import json
from dataclasses import dataclass

from .probes import Result


@dataclass
class InitReport:
    """One init run.

    timestamp is the wall-clock time the run started. fingerprint is what a lock written after
    this run is valid for (runner.fingerprint). results has one entry per probe, in the order
    the probes are listed. blocking names the probes that stop the launch, warnings the ones a
    human should look at, and exit_code is what the pre-task hook exits with: 0 launches the
    agent, 1 refuses.
    """

    timestamp: float
    fingerprint: str
    results: list[Result]
    blocking: list[str]
    warnings: list[str]
    exit_code: int

    def to_json(self) -> str:
        """The text of init_report.json.

        Durations stay out of it, so two runs over the same workbench write the same text
        apart from the timestamp. The run history keeps the timings.
        """
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "fingerprint": self.fingerprint,
                "exit_code": self.exit_code,
                "blocking": self.blocking,
                "warnings": self.warnings,
                "probes": [
                    {"name": r.name, "status": r.status, "detail": r.detail} for r in self.results
                ],
            },
            indent=2,
        ) + "\n"
