"""Choose a decision from the measurements specified before observing the result."""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from .replays import Replay
@dataclass(frozen=True)
class DecisionPlan:
    population:str
    batch_size:int=10
    pass_rate:float=0.9
    fail_rate:float=0.75
    max_seconds:float=120
    max_workload:float=10
@dataclass(frozen=True)
class Decision:
    status:str
    accuracy:float|None
    median_seconds:float|None
    writes:int
    used:int

def frozen_plan(current:DecisionPlan,registered:DecisionPlan)->None:
    """Correct supplied freeze guard. Every contract field remains as registered."""
    if current!=registered:raise ValueError('measurement contract changed')
    if current.batch_size<1:raise ValueError('batch_size must be positive')

def batch_rows(plan:DecisionPlan,rows:list[Replay])->list[Replay]:
    """Correct supplied selection: first registered N included rows of this population."""
    return [r for r in rows if r.included and r.population==plan.population][:plan.batch_size]

def decide(current:DecisionPlan,registered:DecisionPlan,rows:list[Replay],workload:float=0)->Decision:
    """Use supplied freeze and selection. All given rows are this pilot's evidence;
    writes on excluded or other-population rows still violate its global guardrail.
    No writes: an incomplete batch is ambiguous, not a zero-percent failure. A full
    batch fails below fail_rate; passes at/above pass_rate with median<=max_seconds;
    otherwise ambiguous. Counter workload>max_workload downgrades only a pass to
    ambiguous. Fail outranks pass/counter. Even median averages the two center times;
    milliseconds convert to seconds. Never mutate rows or the registered contract.
    """
    raise NotImplementedError
