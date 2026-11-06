"""Outcome decomposition with explicit constraint sets and non-goal identities."""
from __future__ import annotations
from dataclasses import dataclass,field
@dataclass
class Outcome:
    id:str
    user:str=""
    constraints:dict[str,set[str]]=field(default_factory=dict)
    non_goals:tuple[str,...]=()
    children:list["Outcome"]=field(default_factory=list)
@dataclass(frozen=True)
class Resolved:
    id:str
    user:str
    constraints:tuple[tuple[str,tuple[str,...]],...]
    non_goals:tuple[str,...]

def resolve(root:Outcome)->list[Resolved]:
    """Preorder over a tree with unique ids. User inherits from nearest nonblank ancestor;
    no effective user raises ValueError. Named allowed-value constraints inherit; a child
    may add a new constraint or narrow an inherited set, never widen it. Ancestor non-goal
    ids forbid that node anywhere below; each node's non-goals extend the inherited list
    in first-occurrence order. Reject forbidden nodes and relaxation with ValueError.
    Return independent sorted constraint tuples, preserve child order, never change input.
    """
    raise NotImplementedError
