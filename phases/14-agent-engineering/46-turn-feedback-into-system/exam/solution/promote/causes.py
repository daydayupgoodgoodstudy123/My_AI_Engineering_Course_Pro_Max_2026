"""Select effective controls for explicitly identified causes, not for symptoms alone."""
from __future__ import annotations
from dataclasses import dataclass
from .controls import Correction, normalize_cause

LAYERS=("example","test","scope","automation","instruction")
@dataclass(frozen=True)
class Proposal:
    id: str
    target: str
    covers: tuple[str,...]
    rule: str
    verified: bool
@dataclass(frozen=True)
class Selection:
    cause: str
    symptoms: tuple[str,...]
    recurrence: int
    proposal: str|None

def select_controls(corrections:list[Correction],proposals:list[Proposal])->list[Selection]:
    """Group by canonical cause in first-cause order; distinct original symptoms keep
    first-seen order and counts add. Proposal.covers contains canonical cause keys,
    supplied by the investigator. It must be verified, cover that cause and not merely
    repeat any grouped symptom after normalization. Product disagreement accepts only
    human proposals; other causes choose the first effective layer in LAYERS, ties by
    proposal id. A missing effective control has proposal=None, not a prose fallback.
    """
    groups={}
    for c in corrections:
        groups.setdefault(normalize_cause(c.cause),[]).append(c)
    selected=[]
    for cause,items in groups.items():
        symptoms=tuple(dict.fromkeys(c.symptom for c in items))
        human=any("product disagreement" in (c.cause+" "+c.symptom).lower() for c in items)
        valid=[p for p in proposals if p.verified and cause in p.covers
               and normalize_cause(p.rule) not in {normalize_cause(s) for s in symptoms}
               and (p.target=="human" if human else p.target in LAYERS)]
        valid.sort(key=lambda p:(0 if human else LAYERS.index(p.target),p.id))
        selected.append(Selection(cause,symptoms,sum(c.recurrence for c in items),valid[0].id if valid else None))
    return selected
