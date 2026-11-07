"""Typed immutable epistemic, control, durable and bounded higher-order records."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class BeliefKey:
    observer:tuple[str,...]
    subject:tuple[str,...]
    proposition:str
@dataclass(frozen=True,slots=True)
class Observation:
    uid:str
    key:BeliefKey
    value:object
    turn:int
    ordinal:int
    kind:str
@dataclass(frozen=True,slots=True)
class VisibleEvent:
    uid:str
    subject:tuple[str,...]
    proposition:str
    value:object
    turn:int
    ordinal:int
    kind:str
    visible_to:tuple[tuple[str,...],...]
@dataclass(frozen=True,slots=True)
class Agent:
    uid:tuple[str,...]
    name:str
    collected:bool=False
@dataclass(frozen=True,slots=True)
class Target:
    subject:tuple[str,...]
    box:str
@dataclass(frozen=True,slots=True)
class World:
    uid:str
    generation:int
    available:frozenset[str]
@dataclass(frozen=True,slots=True)
class AvailableView:
    world_uid:str
    generation:int
    boxes:tuple[str,...]
@dataclass(frozen=True,slots=True)
class ControlChoice:
    subject:tuple[str,...]
    box:str
@dataclass(frozen=True,slots=True)
class JointReport:
    original_world:World
    view:AvailableView
    choices:tuple[ControlChoice,...]
    taken:tuple[ControlChoice,...]
    duplicate_count:int
    completed:tuple[tuple[str,...],...]
    world:World
    random_state:tuple
@dataclass(frozen=True,slots=True)
class ObservationReceipt:
    event_uid:str
    delivered:tuple[Observation,...]
    visible_records:tuple[Observation,...]
@dataclass(frozen=True,slots=True)
class ReplayRequest:
    population:tuple[Agent,...]
    events:tuple[VisibleEvent,...]
    initial_observations:tuple[Observation,...]
    active_targets:tuple[Target,...]
    completed:tuple[tuple[str,...],...]
    world:World
    seed:int
    now:int
@dataclass(frozen=True,slots=True)
class ReplayReport:
    request:ReplayRequest
    receipts:tuple[ObservationReceipt,...]
    observations:tuple[Observation,...]
    active_targets:tuple[Target,...]
    control:JointReport
@dataclass(frozen=True,slots=True)
class SubjectPrior:
    subject:tuple[str,...]
    believed_available:tuple[str,...]
    preference:tuple[str,...]
@dataclass(frozen=True,slots=True)
class BeliefVersion:
    uid:str
    key:BeliefKey
    value:object
    turn:int
    ordinal:int
    source_uid:str|None
@dataclass(frozen=True,slots=True)
class EpistemicSnapshot:
    uid:str
    population:tuple[Agent,...]
    observations:tuple[Observation,...]
    beliefs:tuple[BeliefVersion,...]
    priors:tuple[SubjectPrior,...]
@dataclass(frozen=True,slots=True)
class SubjectModel:
    subject:tuple[str,...]
    believed_available:tuple[str,...]
    preference:tuple[str,...]
    active:bool
    last_seen_turn:int|None
    source_ids:tuple[str,...]
@dataclass(frozen=True,slots=True)
class Prediction:
    subject:tuple[str,...]
    target:str|None
    source_ids:tuple[str,...]
@dataclass(frozen=True,slots=True)
class ModelDelta:
    key:BeliefKey
    op:str
    value:object
    turn:int
    source_uid:str
@dataclass(frozen=True,slots=True)
class PatchBatch:
    observer:tuple[str,...]
    now:int
    deltas:tuple[ModelDelta,...]
@dataclass(frozen=True,slots=True)
class EpistemicNode:
    uid:str
    agent:tuple[str,...]
    beliefs:tuple[tuple[str,object],...]
    children:tuple[tuple[tuple[str,...],str],...]=()
@dataclass(frozen=True,slots=True)
class BeliefQuery:
    root:str
    subjects:tuple[tuple[str,...],...]
    proposition:str
    max_order:int
@dataclass(frozen=True,slots=True)
class BeliefAnswer:
    status:str
    value:object
    contexts:tuple[str,...]
    requested_order:int
    traversed_order:int
