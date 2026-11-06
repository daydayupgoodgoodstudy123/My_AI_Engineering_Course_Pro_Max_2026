"""Reconstruct the current workflow without silently upgrading weak evidence."""
from __future__ import annotations
from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class Evidence:
    source:str
    observation:str
    level:int
    confidence:float
@dataclass(frozen=True)
class Step:
    order:int
    actor:str
    action:str
    evidence:tuple[Evidence,...]
    friction:str=""
    hidden_state:str=""
    authority:str=""
    exception:bool=False

def supports(evidence:Evidence)->bool:
    """Evidence ladder: level1 direct behavior or level2 artifact proves current behavior;
    reported behavior(level3) and inference(level4) remain useful, unconfirmed leads.
    Confidence never promotes an evidence level.
    """
    return evidence.level in (1,2)

def _grounded(step:Step)->bool:
    return any(supports(e) for e in step.evidence)

def _view(steps:list[Step],position:int)->dict:
    """One step's display, at this input position, preserving every recorded field."""
    return asdict(steps[position])

def audit(steps:list[Step])->dict:
    """Grounded requires a nonempty workflow, valid ordering/evidence and at least one
    level1-2 receipt on every step. Input orders must be1..N in given order, not sorted.
    Invalid confidence/level and missing evidence add issues. direct_percent is the
    percentage of all receipts that are level1-2, rounded half up to an integer; empty
    evidence is0. Issues stay in encounter order; steps preserve all recorded values.
    """
    issues=[]
    if [s.order for s in steps]!=list(range(1,len(steps)+1)):issues.append("workflow order must be contiguous from one")
    for step in steps:
        if not step.evidence:issues.append(f"step {step.order} has no evidence")
        for e in step.evidence:
            if e.level not in (1,2,3,4):issues.append(f"step {step.order} has invalid evidence level")
            if not 0<=e.confidence<=1:issues.append(f"step {step.order} has invalid confidence")
    strong=sum(supports(e) for s in steps for e in s.evidence);total=sum(len(s.evidence) for s in steps)
    percent=(200*strong+total)//(2*total) if total else 0
    grounded=bool(steps) and all(_grounded(s) for s in steps)
    return {"status":"grounded" if not issues and grounded else "needs-evidence","issues":issues,
            "direct_percent":percent,"steps":[_view(steps,i) for i in range(len(steps))]}
