"""Glue the benchmark runner uses: ask a model what it still owes, keep the raw outputs, score them."""
from __future__ import annotations

from collections.abc import Callable

from .mcq import Item, score
from .results import ResultStore


class BenchmarkRun:
    def __init__(self, store: ResultStore, items: list[Item]) -> None:
        self.store = store
        self.items = {item.item_id: item for item in items}

    def run(self, model: str, ask: Callable[[Item], str]) -> int:
        """Ask the model every item it has not answered yet and store the raw outputs.

        A call that raises is stored as a failure (None) and asked again on the next run.
        Returns the number of calls made.
        """
        todo = self.store.pending(model, list(self.items))
        for item_id in todo:
            try:
                output = ask(self.items[item_id])
            except Exception:  # timeouts and API errors: keep going, retry on the next run
                output = None
            self.store.record(model, item_id, output)
        return len(todo)

    def report(self, model: str) -> dict:
        """Score the model's stored outputs (see mcq.score)."""
        outputs = {p.item_id: p.output for p in self.store.predictions(model)}
        return score(list(self.items.values()), outputs)
