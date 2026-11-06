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
    raise NotImplementedError
