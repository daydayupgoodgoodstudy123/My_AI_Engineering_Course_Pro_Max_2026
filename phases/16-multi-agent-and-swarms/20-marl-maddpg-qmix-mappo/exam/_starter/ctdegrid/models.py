"""Immutable local execution, joint training and finite mixer records."""
from dataclasses import dataclass
from fractions import Fraction
@dataclass(frozen=True,slots=True)
class World:
    size:int
    positions:tuple[tuple[int,int],tuple[int,int]]
    pellets:tuple[tuple[int,int],...]
@dataclass(frozen=True,slots=True)
class Observation:
    agent_uid:str
    size:int
    cell:tuple[int,int]
    target:tuple[int,int]
@dataclass(frozen=True,slots=True)
class ActionValue:
    action:str
    value:float
@dataclass(frozen=True,slots=True)
class GridRequest:
    uid:str
    episode:str
    step:int
    world:World
    targets:tuple[tuple[int,int],tuple[int,int]]
    critic_hints:tuple[str,str]=('stay','stay')
@dataclass(frozen=True,slots=True)
class JointTransition:
    uid:str
    episode:str
    step:int
    before:World
    observations:tuple[Observation,Observation]
    local_values:tuple[tuple[ActionValue,...],tuple[ActionValue,...]]
    actions:tuple[str|None,str|None]
    collected:tuple[tuple[int,int]|None,tuple[int,int]|None]
    rewards:tuple[float,float]
    after:World
    done:bool
    policy:str='scripted-local-Q-v1'
@dataclass(frozen=True,slots=True)
class GridReport:
    transitions:tuple[JointTransition,...]
@dataclass(frozen=True,slots=True)
class MixerSpec:
    hidden_weights:tuple[tuple[float,...],...]
    hidden_bias:tuple[float,...]
    state_weights:tuple[tuple[float,float],...]
    activations:tuple[str,...]
    output_weights:tuple[float,...]
    output_bias:float=0.
    output_state:tuple[float,float]=(0.,0.)
@dataclass(frozen=True,slots=True)
class Monotonicity:
    certified:bool
    negative_paths:tuple[str,...]
@dataclass(frozen=True,slots=True)
class JointOracle:
    greedy_actions:tuple[str,...]
    greedy_value:float
    best_actions:tuple[str,...]
    best_value:float
    value_gap:float
    combinations:int
@dataclass(frozen=True,slots=True)
class QRef:
    uid:str
    q_uid:str
@dataclass(frozen=True,slots=True)
class Constant:
    uid:str
    value:float
@dataclass(frozen=True,slots=True)
class Weighted:
    weight:float
    child:object
@dataclass(frozen=True,slots=True)
class Sum:
    uid:str
    bias:float
    terms:tuple[Weighted,...]
@dataclass(frozen=True,slots=True)
class Relu:
    uid:str
    child:object
@dataclass(frozen=True,slots=True)
class Dependency:
    q_uid:str
    coefficients:tuple[Fraction,...]
    certified:bool
@dataclass(frozen=True,slots=True)
class ExpressionFinding:
    code:str
    path:tuple[str,...]
    q_uid:str
@dataclass(frozen=True,slots=True)
class ExpressionAudit:
    uid:str
    value:float|None
    dependencies:tuple[Dependency,...]
    findings:tuple[ExpressionFinding,...]
    children:tuple['ExpressionAudit',...]
