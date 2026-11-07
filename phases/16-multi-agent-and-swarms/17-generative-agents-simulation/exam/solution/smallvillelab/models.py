"""Immutable memory, independent reflection progress, plan and simulated world records."""
from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True,slots=True)
class Memory:
    uid:str
    seq:int
    tick:int
    kind:str
    content:str
    importance:int
    source_ids:tuple[str,...]=()
    contradicts:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class Progress:
    consumed_source_ids:tuple[str,...]=()
    last_reflection_tick:int|None=None
@dataclass(frozen=True,slots=True)
class Belief:
    uid:str
    text:str
    source_ids:tuple[str,...]
@dataclass(frozen=True,slots=True)
class Segment:
    uid:str
    revision:int
    start:int
    end:int
    venue_uid:str
    note:str
    status:str='active'
    cause_ids:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class AgentState:
    uid:str
    name:str
    location:str
    memories:tuple[Memory,...]=()
    progress:Progress=Progress()
    beliefs:tuple[Belief,...]=()
    plans:tuple[Segment,...]=()
@dataclass(frozen=True,slots=True)
class InspectionRequest:
    population:tuple[AgentState,...]
    sender_uid:str
    invitation:str
    now:int
    window:int
    query:str
    threshold:int
@dataclass(frozen=True,slots=True)
class MemoryFeature:
    memory:Memory
    relevance:float
@dataclass(frozen=True,slots=True)
class AgentInspection:
    state:AgentState
    features:tuple[MemoryFeature,...]
    pending_importance:int
    reflection_due:bool
@dataclass(frozen=True,slots=True)
class Inspection:
    request:InspectionRequest
    delivered_to:tuple[str,...]
    agents:tuple[AgentInspection,...]
@dataclass(frozen=True,slots=True)
class TownSnapshot:
    uid:str
    now:int
    wall_origin:Decimal
    agents:tuple[AgentState,...]
@dataclass(frozen=True,slots=True)
class RankedMemory:
    uid:str
    score:float
@dataclass(frozen=True,slots=True)
class ReflectionProposal:
    uid:str
    seq:int
    text:str
    source_ids:tuple[str,...]
@dataclass(frozen=True,slots=True)
class ReflectionResult:
    state:AgentState
    used_source_ids:tuple[str,...]
    rejected_source_ids:tuple[str,...]
    reflection_uid:str|None
@dataclass(frozen=True,slots=True)
class PlanPatch:
    segment_uid:str
    start:int
    end:int
    venue_uid:str
    note:str
    status:str='active'
@dataclass(frozen=True,slots=True)
class RevisionResult:
    state:AgentState
    affected:tuple[str,...]
    changed:tuple[str,...]
    unresolved:tuple[str,...]
@dataclass(frozen=True,slots=True)
class Venue:
    uid:str
    label:str
    capacity:int
    open_intervals:tuple[tuple[int,int],...]
@dataclass(frozen=True,slots=True)
class CalendarObservation:
    agent_uid:str
    segment:Segment
    status:str
@dataclass(frozen=True,slots=True)
class PlanNode:
    uid:str
    agent_uid:str
    start:int
    end:int
    segment_uid:str|None=None
    children:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class BoundNode:
    node:PlanNode
    path:tuple[str,...]
    start:int
    end:int
    segment:Segment|None
    children:tuple['BoundNode',...]
@dataclass(frozen=True,slots=True)
class Movement:
    agent_uid:str
    segment_uid:str
    origin:str
    destination:str
@dataclass(frozen=True,slots=True)
class NodeAudit:
    path:tuple[str,...]
    agent_uid:str
    start:int
    end:int
    segment_uid:str|None
    status:str
    children:tuple['NodeAudit',...]=()
@dataclass(frozen=True,slots=True)
class ExecutionResult:
    reports:tuple[NodeAudit,...]
    world:object
    movements:tuple[Movement,...]
