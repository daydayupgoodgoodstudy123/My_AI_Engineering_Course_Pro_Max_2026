"""A pair of CSV tables is one saved assumption map."""
from __future__ import annotations
import csv
from pathlib import Path
from .model import Assumption, Evidence, Experiment

class MapStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def save(self, items: list[Assumption], experiments: list[Experiment]) -> None:
        """Replace both tables. Preserve input order, raw text/timestamps, optional
        evidence (None differs from empty Evidence), exact float thresholds and types.
        Tables have fixed filenames, so opaque ids never become filesystem paths.
        No atomic multi-file transaction is promised.
        """
        raise NotImplementedError

    def load(self) -> tuple[list[Assumption], list[Experiment]]:
        """Reopen both CSV tables as independent typed objects in saved order."""
        raise NotImplementedError
