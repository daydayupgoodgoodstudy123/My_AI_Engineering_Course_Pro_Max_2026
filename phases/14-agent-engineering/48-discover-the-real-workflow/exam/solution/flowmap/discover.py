"""Find friction, hidden state, authority and exceptions; preserve unconfirmed leads."""
from __future__ import annotations
from dataclasses import dataclass
from .audit import Step,_grounded
@dataclass(frozen=True)
class Finding:
    kind:str
    step:int
    detail:str
    verified:bool
ORDER={"exception":0,"handoff":1,"hidden-state":2,"authority":3,"friction":4}

def discover(steps:list[Step])->list[Finding]:
    """Given valid ordered steps, report explicit exception/friction/authority fields.
    Hidden state is only an explicit memory/chat/personal-notes carrier, never inferred
    merely from missing artifacts. Adjacent actor changes also produce handoff risk.
    A step's findings are verified iff that step has level1-2 evidence; a handoff needs
    both adjacent steps. Weak leads remain in output with verified=False. Sort by ORDER
    then step number. All findings at one step remain; do not average away exceptions.
    """
    result=[]
    for i,s in enumerate(steps):
        verified=_grounded(s)
        if s.exception:result.append(Finding("exception",s.order,s.action,verified))
        if i and s.actor!=steps[i-1].actor:
            previous=steps[i-1];result.append(Finding("handoff",s.order,previous.actor+" -> "+s.actor,verified and _grounded(previous)))
        if s.hidden_state in ("memory","chat","personal-notes"):result.append(Finding("hidden-state",s.order,s.hidden_state,verified))
        if s.authority.strip():result.append(Finding("authority",s.order,s.authority,verified))
        if s.friction.strip():result.append(Finding("friction",s.order,s.friction,verified))
    return sorted(result,key=lambda f:(ORDER[f.kind],f.step))
