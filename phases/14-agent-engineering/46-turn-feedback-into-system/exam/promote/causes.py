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
    raise NotImplementedError
