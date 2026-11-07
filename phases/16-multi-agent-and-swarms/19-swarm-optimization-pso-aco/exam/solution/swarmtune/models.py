"""Typed numeric checkpoints, explicit delayed outcomes and finite routing graph records."""
from dataclasses import dataclass
@dataclass
class Particle:
    uid:str
    x:list[float]
    v:list[float]
    p_best:list[float]
    p_best_fit:float
@dataclass(frozen=True,slots=True)
class ParticleState:
    uid:str
    x:tuple[float,...]
    v:tuple[float,...]
    p_best:tuple[float,...]
    p_best_fit:float
@dataclass(frozen=True,slots=True)
class Best:
    coordinates:tuple[float,...]
    fitness:float
@dataclass(frozen=True,slots=True)
class SwarmState:
    iteration:int
    particles:tuple[ParticleState,...]
    best:Best
    bounds:tuple[tuple[float,float],...]
    rng_state:tuple
    evaluator_version:str='source-ripple-v1'
@dataclass(frozen=True,slots=True)
class Allocation:
    uid:str
    task_uid:str
    task_type:str
    agent_uid:str
@dataclass(frozen=True,slots=True)
class OptimizationJob:
    allocation:Allocation
    state:SwarmState
    iterations:int
    w:float=.6
    c1:float=1.2
    c2:float=1.2
@dataclass(frozen=True,slots=True)
class ChangedStep:
    iteration:int
    particle_uid:str
    x:tuple[float,...]
    v:tuple[float,...]
    fitness:float
    best:Best
@dataclass(frozen=True,slots=True)
class IterationReport:
    iteration:int
    particles:tuple[ParticleState,...]
    current_scores:tuple[float,...]
    population_mean:float
    best:Best
@dataclass(frozen=True,slots=True)
class OptimizationReport:
    job:OptimizationJob
    changed_steps:tuple[ChangedStep,...]
    iterations:tuple[IterationReport,...]
    state:SwarmState
@dataclass(frozen=True,slots=True)
class RouteRow:
    task_type:str
    weights:tuple[tuple[str,float],...]
@dataclass(frozen=True,slots=True)
class RouteTable:
    rows:tuple[RouteRow,...]
    applied_epochs:tuple[int,...]=()
@dataclass(frozen=True,slots=True)
class Outcome:
    uid:str
    allocation_uid:str
    quality:float
    verified:bool
    success:bool
    arrival:int
    epoch:int
@dataclass(frozen=True,slots=True)
class ExperimentCheckpoint:
    uid:str
    state:SwarmState
    table:RouteTable
    allocations:tuple[Allocation,...]
    pending:tuple[Outcome,...]
@dataclass(frozen=True,slots=True)
class RouteChoice:
    task_uid:str
    task_type:str
    agent_uid:str
    draw:float
    total:float
    snapshot:RouteTable
@dataclass(frozen=True,slots=True)
class LearningPolicy:
    threshold:float=.6
    reinforce:float=.2
@dataclass(frozen=True,slots=True)
class LearningDecision:
    outcome_uid:str
    allocation_uid:str
    task_uid:str|None
    task_type:str|None
    agent_uid:str|None
    quality:float
    arrival:int
    epoch:int
    accepted:bool
    amount:float
    reason:str
@dataclass(frozen=True,slots=True)
class LearningResult:
    table:RouteTable
    decision:LearningDecision
@dataclass(frozen=True,slots=True)
class IterationObservation:
    run_uid:str
    report:IterationReport
@dataclass(frozen=True,slots=True)
class RouteObservation:
    choice:RouteChoice
@dataclass(frozen=True,slots=True)
class LearningObservation:
    decision:LearningDecision
@dataclass(frozen=True,slots=True)
class Edge:
    uid:str
    source:str
    target:str
@dataclass(frozen=True,slots=True)
class AntPath:
    uid:str
    start:str
    destination:str
    edges:tuple[str,...]
    decision_uid:str
    epoch:int
@dataclass(frozen=True,slots=True)
class Expedition:
    uid:str
    own_paths:tuple[AntPath,...]
    children:tuple=()
@dataclass(frozen=True,slots=True)
class Trail:
    task_type:str
    destination:str
    edge_uid:str
    weight:float
@dataclass(frozen=True,slots=True)
class TrailState:
    trails:tuple[Trail,...]
    applied_epochs:tuple[int,...]=()
@dataclass(frozen=True,slots=True)
class PathAudit:
    uid:str
    status:str
    visited:tuple[str,...]
    amount:float
@dataclass(frozen=True,slots=True)
class ExpeditionAudit:
    uid:str
    own:tuple[PathAudit,...]
    children:tuple
    before:TrailState
    after:TrailState
@dataclass(frozen=True,slots=True)
class TrailReport:
    reports:tuple[ExpeditionAudit,...]
    state:TrailState
