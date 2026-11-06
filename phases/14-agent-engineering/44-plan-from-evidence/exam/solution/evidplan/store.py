"""A JSON plan source and an append-only JSON Lines progress journal."""
from dataclasses import asdict
import json
from pathlib import Path
from .model import WorkItem, Event


def save_plan(directory: Path, items: list[WorkItem]) -> None:
    """Replace plan.json with the ordered source records, preserving every field."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plan.json").write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False) + "\n", encoding="utf-8")


def load_plan(directory: Path) -> list[WorkItem]:
    """Reopen the JSON source as WorkItem values, restoring tuple-valued fields."""
    rows = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    return [WorkItem(**{**row, "evidence": tuple(row["evidence"]),
                       "depends_on": tuple(row["depends_on"]), "resolvers": tuple(row["resolvers"])}) for row in rows]


def append_event(directory: Path, event: Event) -> None:
    """Append one complete Event to progress.jsonl, retaining repeats and log order."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "progress.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


def load_events(directory: Path) -> list[Event]:
    """Read all journal records in file order; an absent journal means no progress."""
    path = directory / "progress.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [Event(**json.loads(line)) for line in fh]
