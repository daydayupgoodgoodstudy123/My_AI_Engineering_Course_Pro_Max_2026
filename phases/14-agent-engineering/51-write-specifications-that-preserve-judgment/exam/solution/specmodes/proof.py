"""Proof types match specific claims; they are not freely substitutable levels."""
from __future__ import annotations
from dataclasses import dataclass

MATCH={'local':'unit','transport':'wire','interface':'browser','representative':'replay','authority':'audit'}

@dataclass(frozen=True)
class Claim:
    id: str
    kind: str
    cases: tuple[str,...]
    required_receipts: tuple[str,...]
    authority_scope: tuple[str,...] = ()

@dataclass(frozen=True)
class Receipt:
    id: str
    kind: str
    passed: bool
    claim_ids: tuple[str,...]
    cases: tuple[str,...]
    authority_scope: tuple[str,...] = ()

@dataclass(frozen=True)
class ProofResult:
    claim_id: str
    proven: bool
    reasons: tuple[str,...]

def validate_claim(claim: Claim) -> None:
    """Supplied finite coverage schema; no empty-proof vacuous success."""
    if claim.kind not in MATCH or not claim.cases or not claim.required_receipts:
        raise ValueError('claim needs a known kind, cases and required receipts')
    if claim.kind=='authority' and not claim.authority_scope:raise ValueError('authority needs scope')

def verify_claims(claims: list[Claim],receipts: list[Receipt]) -> list[ProofResult]:
    """Retain claim order. Every required receipt must exist, pass, have MATCH kind,
    explicitly bind this claim id, and (authority claims only) name exactly the same
    scope set. For each receipt report only its first error in that order, as
    missing:id / failed:id / kind:id / binding:id / scope:id. Only valid receipts
    contribute case coverage; union coverage must include every declared finite case,
    else append 'cases'. Extra cases/receipts do not hurt. A referenced invalid receipt
    cannot be excused by another valid one. Return proven iff no reasons. IDs unique.
    This verifies the declared finite case universe, not universal real-world safety.
    """
    by_id={r.id:r for r in receipts};results=[]
    for claim in claims:
        validate_claim(claim)
        reasons=[];covered=set()
        for key in claim.required_receipts:
            r=by_id.get(key)
            if r is None:reason='missing:'+key
            elif not r.passed:reason='failed:'+key
            elif r.kind!=MATCH[claim.kind]:reason='kind:'+key
            elif claim.id not in r.claim_ids:reason='binding:'+key
            elif claim.kind=='authority' and set(r.authority_scope)!=set(claim.authority_scope):reason='scope:'+key
            else:reason=''
            if reason:reasons.append(reason)
            else:covered.update(r.cases)
        if not set(claim.cases)<=covered:reasons.append('cases')
        results.append(ProofResult(claim.id,not reasons,tuple(reasons)))
    return results
