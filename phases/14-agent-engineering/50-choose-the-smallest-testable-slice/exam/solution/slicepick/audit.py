"""Detect false minimums relative to the decision's required evidence."""
from __future__ import annotations
from dataclasses import dataclass
from .model import Candidate,StopRule,required_set
from .selection import eligible,choose

@dataclass(frozen=True)
class ProofNeed:
    real_data: bool
    user_value: bool
    exceptions: bool
    repeatable: bool

@dataclass(frozen=True)
class Design:
    candidate: Candidate
    form: str
    user_value: bool
    exceptions: bool
    repeatable: bool
    platform_first: bool
    stop_rule: StopRule

ORDER=('missing-proof','ui-only','infrastructure-only','happy-path','demo-only','platform-first','no-stop-rule')

def effective_stop(rule: StopRule) -> bool:
    """Every action must be nonblank; at least one normalized action must differ
    from 'keep building'. Other nonblank actions are explicit domain instructions.
    """
    actions=[rule.passed,rule.failed,rule.ambiguous]
    return all(x.strip() for x in actions) and any(' '.join(x.casefold().split())!='keep building' for x in actions)

def select_testable(designs: list[Design], required_proof, need: ProofNeed) -> dict:
    """Return {'selected': id-or-None, 'reasons': {id: tuple-of-reasons}}.
    Report every applicable reason in ORDER, retain design order. missing-proof uses
    the supplied normalized coverage gate. ui-only applies only to form='ui' when
    real_data is needed. infrastructure-only/happy-path/demo-only mean their required
    user_value/exceptions/repeatable field is absent. platform_first always blocks.
    An ineffective stop rule also blocks. Only reason-free designs may be scored;
    return None if none remain. Candidate ids are unique. Do not mutate inputs.
    """
    required=required_set(required_proof)
    reasons={};accepted=[]
    for d in designs:
        flags=[]
        if not eligible(d.candidate.slice,required):flags.append('missing-proof')
        if d.form=='ui' and need.real_data:flags.append('ui-only')
        if need.user_value and not d.user_value:flags.append('infrastructure-only')
        if need.exceptions and not d.exceptions:flags.append('happy-path')
        if need.repeatable and not d.repeatable:flags.append('demo-only')
        if d.platform_first:flags.append('platform-first')
        if not effective_stop(d.stop_rule):flags.append('no-stop-rule')
        reasons[d.candidate.id]=tuple(flags)
        if not flags:accepted.append(d.candidate)
    return {'selected':choose(accepted,required).id if accepted else None,'reasons':reasons}
