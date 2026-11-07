"""Typed local service records; not a current A2A wire specification."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class Artifact:
    type:str
    data:object
@dataclass(frozen=True,slots=True)
class TaskEnvelope:
    task_id:str
    state:str
    artifact:Artifact|None
    observed_at:int
@dataclass(frozen=True,slots=True)
class PollRequest:
    task_id:str
    endpoint:str
    deadline:int
    query:str=''
@dataclass(frozen=True,slots=True)
class BatchResult:
    results:tuple[TaskEnvelope,...]
@dataclass(frozen=True,slots=True)
class Attempt:
    task_id:str
    attempt:int
    peer:str
    card_version:str
    envelope:TaskEnvelope
@dataclass(frozen=True,slots=True)
class ReviewResult:
    task_id:str
    modality:str
    issues:tuple[str,...]=()
    lines:int|None=None
    text:str|None=None
@dataclass(frozen=True,slots=True)
class FileReport:
    path:str
    lines:int
@dataclass(frozen=True,slots=True)
class Issue:
    issue_id:str
    file:str
    start:int
    end:int
    text:str
@dataclass(frozen=True,slots=True)
class ReviewGroup:
    group_id:str
    file:str
    start:int
    end:int
    issues:tuple[str,...]=()
    children:tuple['ReviewGroup',...]=()
    schema:str='issue-group-v1'
@dataclass(frozen=True,slots=True)
class ReviewBundle:
    files:tuple[FileReport,...]
    issues:tuple[Issue,...]
    groups:tuple[ReviewGroup,...]
    schema:str='review-tree-v1'
@dataclass(frozen=True,slots=True)
class GroupEntry:
    path:tuple[str,...]
    group:ReviewGroup
@dataclass(frozen=True,slots=True)
class Occurrence:
    path:tuple[str,...]
    group:ReviewGroup
    issue:Issue
@dataclass(frozen=True,slots=True)
class Finding:
    path:tuple[str,...]
    code:str
@dataclass(frozen=True,slots=True)
class GroupAudit:
    group_id:str
    path:tuple[str,...]
    findings:tuple[Finding,...]
    children:tuple['GroupAudit',...]=()
@dataclass(frozen=True,slots=True)
class ReviewAudit:
    modality:str
    unique_issues:int
    memberships:int
    findings:tuple[Finding,...]
    text:str|None=None
    groups:tuple[GroupAudit,...]=()
