"""Compile explicit policy while keeping the rationale behind constraints."""
from __future__ import annotations
from dataclasses import asdict
from .model import Specification,Decision,Boundary,mode,valid_boundary,canonical_limit

def decision_issues(decision: Decision) -> list[str]:
    """Constrained decisions need nonblank rationale. A bounded decision also needs
    an executable typed boundary; rationale alone is not a limit. Delegated rationale
    may be empty at specification time. Invalid modes produce issues, not exceptions.
    """
    issues=[]
    try:kind=mode(decision.mode)
    except ValueError:return ['invalid mode: '+decision.id]
    if kind!='delegated' and not decision.rationale.strip():issues.append('missing rationale: '+decision.id)
    if kind=='bounded' and not decision.rationale.strip():issues.append('missing executable boundary: '+decision.id)
    return issues

def validate(spec: Specification) -> list[str]:
    """Require all six surfaces. Lists require nonblank text. Examples must include
    nonblank normal, edge, failure and forbidden cases (an explicit exercise rule).
    Return field issues then each decision's issues, in declared order.
    """
    issues=[]
    if not spec.outcome.strip():issues.append('outcome is empty')
    for field in ('invariants','non_goals','proof'):
        values=getattr(spec,field)
        if not values or any(not v.strip() for v in values):issues.append(field+' is empty')
    if not spec.examples or any(not e.text.strip() for e in spec.examples):issues.append('examples need four kinds')
    if not spec.decisions:issues.append('decisions is empty')
    for decision in spec.decisions:issues.extend(decision_issues(decision))
    return issues

def compile_allowed(values: tuple[str,...]) -> tuple[tuple[int,str],...]:
    """Compile a dependency/interface catalog as consecutive one-based (ordinal, value)
    entries without mutating its input. Preserve duplicate values and original text;
    compilation must handle large finite catalogs.
    """
    pending=list(values);result=[]
    while pending:result.append((len(result)+1,pending.pop(0)))
    return tuple(result)

def compile_boundary(boundary: Boundary) -> dict:
    """Compile a schema-validated boundary. Numeric limits use canonical units."""
    if boundary.kind=='allowed':return {'kind':'allowed','metric':boundary.metric,'values':compile_allowed(boundary.values)}
    return {'kind':'limit','metric':boundary.metric,'limit':canonical_limit(boundary)}

def compile_contract(spec: Specification) -> dict:
    """Return incomplete with no routes on issues. Otherwise preserve the complete
    original contract and route each decision by id, question and original rationale.
    Bounded routes also contain a compiled boundary. Duplicate questions remain
    separate decisions; rationale must stay bound to the corresponding id.
    """
    issues=validate(spec)
    result={'status':'incomplete' if issues else 'executable','issues':issues,'contract':asdict(spec),
            'delegated':[],'bounded':[],'checkpoints':[]}
    if issues:return result
    for d in spec.decisions:
        kind=mode(d.mode)
        if kind=='delegated':result['delegated'].append({'id':d.id,'question':d.question,'rationale':d.rationale})
        elif kind=='bounded':result['bounded'].append({'id':d.id,'question':d.question,'rationale':d.rationale,'boundary':compile_boundary(d.boundary)})
        else:result['checkpoints'].append({'id':d.id,'question':d.question})
    return result
