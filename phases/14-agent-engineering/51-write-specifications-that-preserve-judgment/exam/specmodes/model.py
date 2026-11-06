"""Six specification surfaces and explicit executable decision boundaries."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Boundary:
    kind: str
    metric: str
    limit: float = 0.0
    values: tuple[str,...] = ()
    unit: str = ''

@dataclass(frozen=True)
class Decision:
    id: str
    question: str
    mode: str
    rationale: str
    boundary: Boundary | None = None

@dataclass(frozen=True)
class Example:
    kind: str
    text: str

@dataclass(frozen=True)
class Specification:
    outcome: str
    invariants: tuple[str,...]
    examples: tuple[Example,...]
    non_goals: tuple[str,...]
    decisions: tuple[Decision,...]
    proof: tuple[str,...]

def mode(value: str) -> str:
    """Supplied case/edge-space normalization; no policy inferred from a question."""
    result=value.strip().casefold()
    if result not in ('locked','bounded','delegated'):raise ValueError('unknown decision mode')
    return result

def valid_boundary(boundary: Boundary | None) -> bool:
    """Supplied typed schema: a positive finite limit, or a nonempty exact allowlist.
    Count limits use no unit; elapsed limits use s or ms. An allowlist can bound
    dependency/interface choices without any numeric quantity.
    """
    if boundary is None:return False
    if boundary.kind=='allowed':
        return boundary.metric in ('dependency','interface') and bool(boundary.values) and all(v.strip() for v in boundary.values)
    return (boundary.kind=='limit' and boundary.metric in ('sources','retries','elapsed')
            and type(boundary.limit) in (int,float) and math.isfinite(boundary.limit) and boundary.limit>0
            and (boundary.unit in ('s','ms') if boundary.metric=='elapsed' else boundary.unit==''))

def canonical_limit(boundary: Boundary) -> float:
    """Supplied: numeric contexts use seconds and counts, never wall-clock text."""
    return boundary.limit/1000 if boundary.metric=='elapsed' and boundary.unit=='ms' else boundary.limit

def decode_boundary(raw) -> Boundary | None:
    """Supplied JSON model rehydration; histories retain raw units/values."""
    if raw is None:return None
    return Boundary(raw['kind'],raw['metric'],raw['limit'],tuple(raw['values']),raw['unit'])

def decode_decision(raw: dict) -> Decision:
    """Supplied model rehydration; rationale and mode text remain verbatim."""
    return Decision(raw['id'],raw['question'],raw['mode'],raw['rationale'],decode_boundary(raw['boundary']))
