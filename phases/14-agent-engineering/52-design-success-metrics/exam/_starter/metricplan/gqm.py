"""Trace metrics through explicit questions and goals, without averaging away failure."""
from __future__ import annotations
from dataclasses import dataclass
from .contract import Metric,duplicate_names
@dataclass(frozen=True)
class Question:
    id:str
    metrics:tuple[str,...]
@dataclass(frozen=True)
class Goal:
    id:str
    questions:tuple[Question,...]=()
    children:tuple[Goal,...]=()
RANK={'pass':0,'ambiguous':1,'fail':2}

def catalog(metrics:list[Metric],states:dict[str,str])->dict[str,Metric]:
    """Correct supplied identity/status schema. Goal structure is a finite tree;
    metric leaves may be shared references. Question/goal ids are unique per sibling.
    """
    if duplicate_names(m.name for m in metrics):raise ValueError('duplicate metric')
    if any(s not in RANK for s in states.values()):raise ValueError('invalid metric status')
    return {m.name:m for m in metrics}

def trace(root:Goal,metrics:list[Metric],states:dict[str,str])->dict:
    """Return status, questions (path,status), orphans and issues. Traverse own
    questions then children in input order; paths are tuples of goal ids then question
    id. Each question has >=1 metric ref; unknown refs add 'unknown:path:metric'. Empty
    questions add 'empty:path'. Unknown/missing states are ambiguous. A question and
    goal take the worst state (fail>ambiguous>pass); empty goals are ambiguous. Shared
    metric refs serve every question, not duplicate definitions. Orphans are catalog
    names never referenced, in catalog order, with 'orphan:name' issues. Only the whole
    root plan needs >=1 outcome and guardrail among referenced known metrics; append
    'missing-kind:kind' in that order. Single risk questions/subgoals may be guardrail
    only. Any issue makes an otherwise pass ambiguous; fail remains fail. No mutation.
    """
    raise NotImplementedError
