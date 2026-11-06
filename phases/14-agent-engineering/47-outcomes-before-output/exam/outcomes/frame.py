"""Outcome framing keeps the result independent of a proposed output."""
from __future__ import annotations
from dataclasses import dataclass,field

@dataclass(frozen=True)
class Constraint:
    text: str
    technology: str=""

@dataclass
class Frame:
    user: str
    situation: str
    current_behavior: str
    desired_outcome: str
    constraints: list[Constraint]
    non_goals: list[str]
    proposed_output: str=""

class Compatibility:
    """A fixed snapshot of technology-to-reason receipts. Entries have unique names;
    an unrelated technology's receipt never fixes this technology. Snapshot is immutable.
    """
    def __init__(self,entries:list[tuple[str,str]]):
        self.entries=tuple(entries)
    def reason_for(self,technology:str)->str:
        """Return this exact technology's receipt, or empty text when absent."""
        return next((reason for name,reason in self.entries if name==technology),"")

def _names_output(frame:Frame,aliases:dict[str,tuple[str,...]])->bool:
    """Match the proposed output's finite supplied aliases in the desired outcome,
    ignoring case and runs of whitespace. Alias equivalence is data, not inferred NLP.
    No proposed output means there is nothing to match.
    """
    if not frame.proposed_output: return False
    options=aliases.get(frame.proposed_output,(frame.proposed_output,))
    text=" ".join(frame.desired_outcome.lower().split())
    return frame.proposed_output.lower() in frame.desired_outcome.lower()

def validate(frame:Frame,compatibility:Compatibility,aliases:dict[str,tuple[str,...]])->list[str]:
    """Return issues in fixed field order, followed by output leakage and constraints.
    Nonempty user/situation/current_behavior/desired_outcome are required. Constraints
    and non_goals each need a nonblank item and may not contain blank items. Each named
    technology needs its own nonblank compatibility receipt. Only desired_outcome is
    checked for proposed-output leakage; a fixed technology may occur in constraints.
    """
    issues=[]
    for name in ("user","situation","current_behavior","desired_outcome"):
        if not getattr(frame,name).strip(): issues.append(name+" is empty")
    if not frame.constraints:
        issues.append("constraints need nonblank items")
    if not frame.non_goals:
        issues.append("non-goals need nonblank items")
    if _names_output(frame,aliases): issues.append("desired outcome names the proposed output")
    for c in frame.constraints:
        if c.technology and not any(reason.strip() for name,reason in compatibility.entries):
            issues.append("technology lacks compatibility evidence: "+c.technology)
    return issues

def decision(frame:Frame,compatibility:Compatibility,aliases:dict[str,tuple[str,...]])->dict:
    """Frame status and the next evidence question. A missing user has no question."""
    issues=validate(frame,compatibility,aliases)
    return {"status":"needs-framing" if issues else "ready-to-discover","issues":issues,
            "next_question":f"What evidence would show that the desired outcome was achieved for the {frame.user}?" if frame.user.strip() else None}
