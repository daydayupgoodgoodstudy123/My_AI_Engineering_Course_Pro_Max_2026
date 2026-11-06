"""What the CI job runs on every push: run the suite, store the snapshot, gate against main."""
from __future__ import annotations

from collections.abc import Callable

from .gate import GateReport, gate
from .harness import EvalCase, FlakyTracker, run_suite
from .store import CaseRecord, Snapshot, SnapshotStore


class EvalPipeline:
    def __init__(self, store: SnapshotStore, limits: dict[str, int], window: int = 5) -> None:
        self.store = store
        self.limits = limits
        self.tracker = FlakyTracker(window)

    def run(self, sha: str, factories: list[Callable[[], EvalCase]], on_main: bool) -> Snapshot:
        """Run every case once on a commit and store the snapshot.

        Only main's runs feed the flaky tracker: a pull request that breaks a case must show up
        as a regression, not as a case that started to flake.
        """
        results = run_suite(factories)
        if on_main:
            for result in results:
                self.tracker.record(result)
        flaky = self.tracker.flaky()
        snapshot = Snapshot(
            sha,
            tuple(
                CaseRecord(r.cid, r.category, r.passed, r.rounds, r.cid in flaky, r.reason)
                for r in results
            ),
        )
        self.store.save(snapshot)
        return snapshot

    def check(self, sha: str, main_history: list[str]) -> GateReport:
        """Gate a commit against main's newest snapshot."""
        return gate(self.store.load(sha), self.store.baseline(main_history), self.limits)
