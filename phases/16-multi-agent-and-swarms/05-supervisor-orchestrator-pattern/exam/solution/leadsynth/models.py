from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Claim:
    claim_id:str
    value:str
    source_ids:tuple[str,...]
    topic:str

@dataclass(frozen=True)
class Task:
    question_id:str
    question:str
    scope:tuple[str,...]
    token_cap:int

@dataclass(frozen=True)
class Observation:
    summary:str
    tokens:int
    seconds:float
    working_context:list[str]
    claims:tuple[Claim,...]=()

@dataclass(frozen=True)
class Artifact:
    question_id:str
    question:str
    scope:tuple[str,...]
    summary:str
    tokens:int
    seconds:float
    cut:bool=False
    claims:tuple[Claim,...]=()
