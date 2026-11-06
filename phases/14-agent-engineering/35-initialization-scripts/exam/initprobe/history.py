"""The init run history: one JSON line per run, for the human who has to work out why init
refused to launch."""
from __future__ import annotations

from pathlib import Path

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
        raise NotImplementedError

    def runs(self) -> list[InitReport]:
        """Every run on disk now, in the order they were appended. A missing file holds no runs.

        A line that is not a run raises ValueError naming its line number ("line 3"): a history
        that skips what it cannot read hides the run someone is looking for.
        """
        raise NotImplementedError

    def last_ready(self) -> InitReport | None:
        """The most recent run that let the agent launch (exit_code 0), or None."""
        raise NotImplementedError

    def close(self) -> None:
        """Release anything the history holds open."""
