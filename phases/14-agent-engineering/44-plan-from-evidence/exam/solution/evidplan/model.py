"""Plan and progress records; log position defines event order."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkItem:
    id: str
    change: str
    evidence: tuple[str, ...]
    depends_on: tuple[str, ...]
    proof: str
    irreversible: bool = False
    resolvers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Event:
    kind: str
    item: str
    proof: str = ""
    exit_code: int | None = None
    summary: str = ""
    path: str = ""
