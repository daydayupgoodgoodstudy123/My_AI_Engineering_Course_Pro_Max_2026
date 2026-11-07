from dataclasses import dataclass
from enum import Enum

class Status(str,Enum):
    VERIFIED='verified'
    UNKNOWN='unknown'
    NEGATIVE='negative'
    MISSING='missing'
    CONFLICT='conflict'

@dataclass(frozen=True)
class Leaf:
    leaf_id:str
    worker:str
    obligation:str
    department:str
    question:str
    answer:str
    status:Status
    citation_ids:tuple[str,...]

@dataclass(frozen=True)
class Branch:
    branch_id:str
    status:Status
    leaf_ids:tuple[str,...]

@dataclass(frozen=True)
class Node:
    node_id:str
    department:str|None
    obligations:tuple[str,...]
    children:tuple[str,...]
    bindings:tuple[tuple[str,str,str],...]
    leaf_ids:tuple[str,...]
    summary:str
    available:bool=True

@dataclass(frozen=True)
class Dossier:
    original_question:str
    obligations:tuple[tuple[str,str],...]
    root_id:str
    nodes:dict[str,Node]
    leaves:dict[str,Leaf]
