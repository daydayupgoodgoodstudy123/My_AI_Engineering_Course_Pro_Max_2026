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
    by_name=catalog(metrics,states);seen=set();questions=[];issues=[]
    def worst(values):return max(values,key=RANK.get) if values else 'ambiguous'
    def walk(goal,path):
        path=path+(goal.id,);values=[]
        for q in goal.questions:
            where=path+(q.id,);found=[]
            if not q.metrics:issues.append('empty:'+ '/'.join(where))
            for name in q.metrics:
                if name not in by_name:issues.append('unknown:'+ '/'.join(where)+':'+name);found.append('ambiguous')
                else:seen.add(name);found.append(states.get(name,'ambiguous'))
            state=worst(found);questions.append((where,state));values.append(state)
        values.extend(walk(child,path) for child in goal.children)
        return worst(values)
    status=walk(root,());orphans=tuple(name for name in by_name if name not in seen)
    issues.extend('orphan:'+name for name in orphans)
    kinds={by_name[n].kind for n in seen}
    for kind in ('outcome','guardrail'):
        if kind not in kinds:issues.append('missing-kind:'+kind)
    if issues and status=='pass':status='ambiguous'
    return {'status':status,'questions':questions,'orphans':orphans,'issues':issues}
