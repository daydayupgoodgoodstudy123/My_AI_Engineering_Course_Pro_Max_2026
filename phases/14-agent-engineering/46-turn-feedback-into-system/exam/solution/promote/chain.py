"""Why-chains point to explicit effective owners; they do not infer real causality."""
from __future__ import annotations
from dataclasses import dataclass,field
from .controls import normalize_cause

@dataclass
class Cause:
    name: str
    owner: str|None=None
    effective: bool=False
    why: list["Cause"]=field(default_factory=list)

@dataclass(frozen=True)
class Placement:
    cause: str
    owner: str
    symptoms: tuple[str,...]

def place_controls(observations:list[tuple[str,Cause]])->list[Placement]:
    """For each symptom, traverse its cause DAG and choose the deepest node having a
    nonempty owner AND effective=True. Break depth ties by canonical cause name, then
    owner. Depth is measured along each path, so a shared node may occur at different
    depths. Group equal (canonical name, owner), preserving first symptom order without
    duplicates; return groups sorted by that pair. A symptom with no effective owned
    cause raises ValueError. Input DAGs are acyclic and remain unchanged.
    """
    grouped={}
    for symptom,root in observations:
        choices=[]
        def walk(node,depth):
            if node.owner and node.effective:
                choices.append((depth,normalize_cause(node.name),node.owner))
            for child in node.why: walk(child,depth+1)
        walk(root,0)
        if not choices: raise ValueError("no effective owned cause")
        depth,name,owner=min(choices,key=lambda c:(-c[0],c[1],c[2]))
        symptoms=grouped.setdefault((name,owner),[])
        if symptom not in symptoms: symptoms.append(symptom)
    return [Placement(name,owner,tuple(grouped[(name,owner)])) for name,owner in sorted(grouped)]
