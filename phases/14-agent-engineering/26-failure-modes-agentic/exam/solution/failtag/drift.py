"""Mode rates, the CI gate, and drift alerts against the last-known-good baseline."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from .store import TraceStore


@dataclass(frozen=True)
class Alert:
    mode: str
    baseline: float
    current: float


def mode_rates(label_lists: list[list[str]]) -> dict[str, float]:
    """Share of traces tagged with each mode.

    Clean traces count in the denominator, and a trace counts once per mode.
    """
    n = len(label_lists)
    counts = Counter(mode for labels in label_lists for mode in set(labels))
    return {mode: count / n for mode, count in counts.items()}


def build_gate(label_lists: list[list[str]], threshold: float = 0.05) -> list[str]:
    """Modes that fail the build: tagged on at least threshold of the traces, sorted.

    A mode fails when count / n >= threshold. An empty run fails nothing.
    """
    if not label_lists:
        return []
    return sorted(mode for mode, rate in mode_rates(label_lists).items() if rate >= threshold)


class DriftMonitor:
    """Pages when a failure mode gets worse than it was on the last-known-good traces."""

    def __init__(
        self,
        store: TraceStore,
        clock: Callable[[], float],
        *,
        tolerance: float = 0.05,
        min_traces: int = 20,
        cooldown_s: float = 600.0,
    ) -> None:
        self.store = store
        self.clock = clock
        self.tolerance = tolerance
        self.min_traces = min_traces
        self.cooldown_s = cooldown_s
        self._last_page: dict[str, float] = {}

    def confirm(self, tids: list[str]) -> None:
        """Accept these traces as the new last-known-good baseline."""
        self.store.set_baseline(tids)

    def check(self, tids: list[str]) -> list[Alert]:
        """Compare the traces in tids with the baseline and return the alerts to page now.

        - With no baseline there is nothing to compare against: raise LookupError.
        - Fewer than min_traces traces give no verdict: return [].
        - A mode drifts when its current rate is more than tolerance above its baseline
          rate; a mode missing from the baseline has rate 0. Falling rates are not drift.
        - Only confirm() moves the baseline.
        - Each mode pages at most once per cooldown_s of clock() time, counted from the
          last time it paged. Alerts come sorted by mode.
        """
        good = self.store.baseline()
        if good is None:
            raise LookupError("no last-known-good baseline to compare against")
        if len(tids) < self.min_traces:
            return []
        before = mode_rates([self.store.get(tid)[1] for tid in good]) if good else {}
        now_rates = mode_rates([self.store.get(tid)[1] for tid in tids])
        now = self.clock()
        alerts = []
        for mode in sorted(now_rates):
            base = before.get(mode, 0.0)
            if now_rates[mode] - base <= self.tolerance:
                continue
            last = self._last_page.get(mode)
            if last is not None and now - last < self.cooldown_s:
                continue
            self._last_page[mode] = now
            alerts.append(Alert(mode, base, now_rates[mode]))
        return alerts
