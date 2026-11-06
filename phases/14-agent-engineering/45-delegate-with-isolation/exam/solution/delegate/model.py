"""A worker returns proof material, not an authoritative success claim."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkUnit:
    id: str
    owner: str
    paths: tuple[str, ...]
    depends_on: tuple[str, ...]
    proof: str
    read_only: bool = False


@dataclass(frozen=True)
class Proof:
    command: str
    exit_code: int | None
    output: str


@dataclass(frozen=True)
class Handoff:
    unit: str
    changed: tuple[str, ...]
    proof: Proof
    claimed_passed: bool = True
