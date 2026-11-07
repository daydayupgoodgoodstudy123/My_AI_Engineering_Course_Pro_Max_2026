from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

@dataclass(frozen=True,slots=True)
class Incident:
    uid:str
    root:str
    primary:str
    symptoms:dict

@dataclass(frozen=True,slots=True)
class Detection:
    uid:str
    root:str
    primary_value:object
    category:str
    tags:tuple

@dataclass(frozen=True,slots=True)
class Observation:
    action_uid:str
    at:int
    cleared:object
    note:str

@dataclass(frozen=True,slots=True)
class IncidentRecord:
    uid:str
    root:str
    primary:str
    symptoms:dict
    category:str
    tags:tuple
    action:str
    call_budget:int
    validation:Observation

@dataclass(frozen=True,slots=True)
class ReplayReport:
    decisions:tuple
    final_window:tuple
    state:str
    failures:int

@dataclass(frozen=True,slots=True)
class CallNode:
    uid:str
    service:str
    children:tuple=()
    attempts:int=1

@dataclass(frozen=True,slots=True)
class Invocation:
    uid:str
    service:str
    status:str
    actual:bool
    success:object
    at:int
    remaining:int

@dataclass(frozen=True,slots=True)
class AttemptTrace:
    ordinal:int
    children:tuple
    invocation:Invocation

@dataclass(frozen=True,slots=True)
class NodeTrace:
    uid:str
    service:str
    status:str
    tries:tuple

@dataclass(frozen=True,slots=True)
class CascadeReport:
    root:str
    incident:str
    nodes:tuple
    used:int
    remaining:int
    calls:tuple
    effects:tuple

@dataclass(frozen=True,slots=True)
class PhaseEvent:
    uid:str
    incident:IncidentRecord
    phase:str
    observation:object=None

@dataclass(frozen=True,slots=True)
class EdgeAudit:
    attempt:int
    child:str
    audit:object

@dataclass(frozen=True,slots=True)
class AmplificationAudit:
    uid:str
    service:str
    status:str
    own_calls:int
    total_calls:int
    own_shortcircuits:int
    total_shortcircuits:int
    own_budget_blocks:int
    total_budget_blocks:int
    attempts:tuple
    edges:tuple

@dataclass(frozen=True,slots=True)
class CascadeAudit:
    root:str
    incident:str
    roots:tuple
    actual_calls:int
    distinct_services:tuple
    amplification:Fraction
    shortcircuits:tuple
    budget_blocks:tuple
