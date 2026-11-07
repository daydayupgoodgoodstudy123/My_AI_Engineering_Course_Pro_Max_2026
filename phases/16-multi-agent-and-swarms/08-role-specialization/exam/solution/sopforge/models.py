"""Typed local replay records; no provider protocol or real agent runtime."""
from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True)
class Case:
    case_id:str
    args:tuple
    expected:Any
@dataclass(frozen=True)
class FieldRule:
    name:str
    owner:str
    required:bool=True
@dataclass(frozen=True)
class Spec:
    spec_id:str
    revision:int
    task_name:str
    signature:str
    description:str
    cases:tuple[Case,...]
    fields:tuple[tuple[str,Any],...]=()
    rules:tuple[FieldRule,...]=()
@dataclass(frozen=True)
class Artifact:
    artifact_id:str
    revision:int
    spec_id:str
    spec_revision:int
    code:str
@dataclass(frozen=True)
class CriticReport:
    spec_id:str
    spec_revision:int
    artifact_id:str
    artifact_revision:int
    approved:bool
    notes:tuple[str,...]
@dataclass(frozen=True)
class CaseEvidence:
    case_id:str
    args:tuple
    expected:Any
    got:Any
    kind:str
    error_type:str=''
    error_message:str=''
@dataclass(frozen=True)
class VerifierReport:
    spec_id:str
    spec_revision:int
    artifact_id:str
    artifact_revision:int
    source_digest:str
    executed:bool
    passed:bool
    cases:tuple[CaseEvidence,...]
    load_error:tuple[str,str]|None=None
@dataclass(frozen=True)
class Bundle:
    spec:Spec
    artifact:Artifact
    critic:CriticReport
    verifier:VerifierReport
@dataclass(frozen=True)
class Snapshot:
    specs:tuple[Spec,...]
    bundles:tuple[Bundle,...]
@dataclass(frozen=True)
class Step:
    step_id:str
    requires:tuple[str,...]
    bundle:Bundle|None=None
    runs:int=0
    status:str='waiting'
@dataclass(frozen=True)
class Question:
    question_id:str
    spec_id:str
    spec_revision:int
    step_id:str
    field:str
    owner:str
@dataclass(frozen=True)
class Answer:
    question_id:str
    spec_id:str
    spec_revision:int
    field:str
    owner:str
    value:Any
@dataclass(frozen=True)
class PipelineState:
    spec:Spec
    history:tuple[Spec,...]
    steps:tuple[Step,...]
    questions:tuple[Question,...]=()
    blocked_step:str|None=None
@dataclass(frozen=True)
class CaseEntry:
    classname:str
    name:str
    kind:str
    message:str
    body:str
@dataclass(frozen=True)
class RoleRecord:
    handle:str
    producer:str
    kind:str
    payload:Any
@dataclass(frozen=True)
class SOPStage:
    name:str
    role:str
    inputs:tuple[tuple[str,str],...]
    outputs:tuple[tuple[str,str],...]
    exposes:tuple[str,...]
    children:tuple['SOPStage',...]=()
