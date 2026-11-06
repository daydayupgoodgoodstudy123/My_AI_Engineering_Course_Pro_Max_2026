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
    raise NotImplementedError

def select_testable(designs: list[Design], required_proof, need: ProofNeed) -> dict:
    """Return {'selected': id-or-None, 'reasons': {id: tuple-of-reasons}}.
    Report every applicable reason in ORDER, retain design order. missing-proof uses
    the supplied normalized coverage gate. ui-only applies only to form='ui' when
    real_data is needed. infrastructure-only/happy-path/demo-only mean their required
    user_value/exceptions/repeatable field is absent. platform_first always blocks.
    An ineffective stop rule also blocks. Only reason-free designs may be scored;
    return None if none remain. Candidate ids are unique. Do not mutate inputs.
    """
    raise NotImplementedError
