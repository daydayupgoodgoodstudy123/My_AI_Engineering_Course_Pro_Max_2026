"""Typed assumptions and pre-registered, finite-sample experiments."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Evidence:
    verdict: str
    text: str

@dataclass(frozen=True)
class Assumption:
    id: str
    kind: str
    statement: str
    impact: int
    uncertainty: int
    irreversibility: int
    evidence: Evidence | None = None

@dataclass(frozen=True)
class Experiment:
    id: str
    assumption_id: str
    population: str
    observable: str
    direction: str
    threshold: float
    sample_size: int
    registered_at: str
    pass_action: str
    fail_action: str
    ambiguous_action: str

@dataclass(frozen=True)
class Sample:
    at: str
    value: float

@dataclass(frozen=True)
class Outcome:
    status: str
    decision: str
    uncertainty: int

KINDS = ('value','usability','feasibility','viability','safety')

def strict_dimension(value: int) -> int:
    """Supplied: dimensions are actual integers in 1..5, never bool/float."""
    if type(value) is not int or not 1 <= value <= 5:
        raise ValueError('risk dimensions must be integers from one to five')
    return value

def risk_score(item: Assumption) -> int:
    """Supplied example score, not a universal risk formula."""
    return strict_dimension(item.impact) * strict_dimension(item.uncertainty) + strict_dimension(item.irreversibility)

def instant(text: str) -> datetime:
    """Supplied: compare aware ISO instants; preserve original strings in storage."""
    result = datetime.fromisoformat(text[:-1] + '+00:00' if text.endswith('Z') else text)
    if result.utcoffset() is None:
        raise ValueError('timestamps must be aware')
    return result

def validate_experiment(exp: Experiment) -> None:
    """Supplied structured falsifiability checks; no free-text number guessing."""
    if not all(x.strip() for x in (exp.id,exp.assumption_id,exp.population,exp.observable)):
        raise ValueError('experiment needs identity, population and observable')
    if exp.direction not in ('at-least','at-most') or type(exp.sample_size) is not int or exp.sample_size < 1:
        raise ValueError('invalid experiment direction or sample size')
    instant(exp.registered_at)
    if not all(x.strip() for x in (exp.pass_action,exp.fail_action,exp.ambiguous_action)):
        raise ValueError('every outcome needs an action')
