"""A JSON plan source and an append-only JSON Lines progress journal."""
from dataclasses import asdict
import json
from pathlib import Path
from .model import WorkItem, Event


def save_plan(directory: Path, items: list[WorkItem]) -> None:
    """Replace plan.json with the ordered source records, preserving every field."""
    raise NotImplementedError


def load_plan(directory: Path) -> list[WorkItem]:
    """Reopen the JSON source as WorkItem values, restoring tuple-valued fields."""
    raise NotImplementedError


def append_event(directory: Path, event: Event) -> None:
    """Append one complete Event to progress.jsonl, retaining repeats and log order."""
    raise NotImplementedError


def load_events(directory: Path) -> list[Event]:
    """Read all journal records in file order; an absent journal means no progress."""
    raise NotImplementedError
