"""Required proof gates scoring; reversible slices learn at lower consequence."""
from __future__ import annotations
from dataclasses import asdict
from .model import Slice, Candidate, normalized_proofs, required_set, validate_numbers

def score(item: Slice) -> float:
    """Positive effort only. Reversible consequence costs 0.5 per unit, irreversible
    costs 2. Return (value + uncertainty reduced)/(effort + penalty), rounded to 3 decimals.
    """
    validate_numbers(item)
    if item.effort < 0: raise ValueError('effort must be positive')
    risk_penalty=item.consequence*(0.5 if not item.reversible else 2)
    return round((item.outcome_value+item.uncertainty_reduced)/(item.effort+risk_penalty),3)

def eligible(item: Slice, required: set[str]) -> bool:
    """Cover every normalized required proof, allowing extra/duplicate raw proofs."""
    offered=normalized_proofs(item.proves)
    return all(proof in offered for proof in required)

def choose(items: list[Candidate], required_proof) -> Candidate:
    """Gate by nonempty required proof first. Maximize score, then lower effort,
    then lexicographically larger name and id. IDs are unique. Inputs are untouched.
    """
    required=required_set(required_proof)
    candidates=[item for item in items if eligible(item.slice,required)]
    if not candidates: raise ValueError('no slice proves the required assumptions')
    return max(candidates,key=lambda c:(score(c.slice),-c.slice.effort,c.slice.name,c.id))

def decision(items: list[Candidate], required_proof) -> dict:
    """Return selected and alternatives by stable candidate identity. Alternatives
    retain input order, including equal-content candidates with different ids and
    ineligible candidates. Raw proof order/duplicates remain in report payloads.
    """
    selected=choose(items,required_proof)
    def row(c):return {'id':c.id,**asdict(c.slice),'score':score(c.slice)}
    return {'required_proof':sorted(required_set(required_proof)), 'selected':row(selected),
            'alternatives':[row(item) for item in items if item.slice != selected.slice]}
