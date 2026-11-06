"""Incremental observations; logfmt output with supplied JSON value quoting."""
from __future__ import annotations
import json
from collections.abc import AsyncIterable, AsyncIterator
from .model import Assumption, Experiment, Sample
from .experiments import judge

class SampleBook:
    """Supplied correct keyed accumulator. Freeze each experiment at its first N
    samples and report its id once. Unknown ids are rejected. completed() accounts
    for every declared experiment; pending() retains declared order.
    """
    def __init__(self, experiments: list[Experiment]):
        self.experiments = {x.id:x for x in experiments}
        self.samples = {x.id:[] for x in experiments}
        self.closed: set[str] = set()
    def feed(self, key: str, sample: Sample) -> bool:
        exp = self.experiments[key]
        if key in self.closed: return False
        self.samples[key].append(sample)
        if len(self.samples[key]) == exp.sample_size:
            self.closed.add(key)
            return True
        return False
    def completed(self) -> bool:
        return len(self.closed) == len(self.experiments)
    def pending(self) -> list[str]:
        return [key for key in self.experiments if key not in self.closed]

def log_line(key: str, outcome) -> str:
    """Supplied logfmt encoder: every value is a JSON scalar, one newline."""
    data = {'experiment':key,'status':outcome.status,'decision':outcome.decision,'uncertainty':outcome.uncertainty}
    return ' '.join(k+'='+json.dumps(v,ensure_ascii=False) for k,v in data.items())+'\n'

async def stream_experiments(items: list[Assumption], experiments: list[Experiment], source: AsyncIterable[tuple[str,Sample]]) -> AsyncIterator[str]:
    """For each first complete batch, immediately yield its judged logfmt line.
    Emit before pulling the next observation; stop without future pulls when all
    experiments complete. At EOF, emit ambiguous partial/empty batches in declared
    experiment order. Empty experiment lists consume nothing. Closing after a yield
    consumes nothing further. Use the supplied book/encoder; inputs have unique ids.
    """
    raise NotImplementedError
    yield ''
