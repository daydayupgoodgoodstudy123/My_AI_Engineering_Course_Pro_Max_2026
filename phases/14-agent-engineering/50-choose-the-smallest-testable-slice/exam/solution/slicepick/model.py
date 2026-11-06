"""Evidence-producing workflow candidates with stable decision identities."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Slice:
    name: str
    outcome_value: int
    uncertainty_reduced: int
    effort: int
    consequence: int
    reversible: bool
    proves: tuple[str,...]

@dataclass(frozen=True)
class Candidate:
    id: str
    slice: Slice

@dataclass(frozen=True)
class StopRule:
    passed: str
    failed: str
    ambiguous: str

@dataclass(frozen=True)
class Snapshot:
    required_proof: tuple[str,...]
    candidates: tuple[Candidate,...]
    selected_id: str
    selected_score: float
    stop_rule: StopRule

def normalized_proofs(values) -> tuple[str,...]:
    """Supplied comparison vocabulary: strip/casefold; preserve raw values elsewhere."""
    return tuple(value.strip().casefold() for value in values)

def required_set(values) -> set[str]:
    """Supplied: at least one nonblank required proof, never a vacuous proof gate."""
    result=set(normalized_proofs(values))
    if not result or '' in result: raise ValueError('required proof must be nonempty')
    return result

def validate_numbers(item: Slice) -> None:
    """Supplied type/range checks; effort zero is left for score's positive check."""
    for value in (item.outcome_value,item.uncertainty_reduced,item.effort,item.consequence):
        if type(value) is not int or value<0: raise ValueError('dimensions must be nonnegative integers')
    if type(item.reversible) is not bool: raise ValueError('reversible must be bool')
