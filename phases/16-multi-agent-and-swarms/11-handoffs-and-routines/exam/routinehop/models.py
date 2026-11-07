"""Typed local calls and immutable control receipts; not an SDK wire protocol."""
from dataclasses import dataclass
from typing import Callable
@dataclass(frozen=True,slots=True)
class Tool:
    name:str
    invoke:Callable
@dataclass(frozen=True,slots=True)
class Agent:
    name:str
    instructions:str
    functions:tuple[Tool,...]=()
@dataclass(frozen=True,slots=True)
class ToolCall:
    call_id:str
    tool:str
    arguments:tuple[tuple[str,object],...]=()
@dataclass(frozen=True,slots=True)
class BoundCall:
    owner:Agent
    call:ToolCall
    function:Tool
@dataclass(frozen=True,slots=True)
class AskForOrder:
    text:str='Please provide your order id.'
@dataclass(frozen=True,slots=True)
class ReadyRefund:
    order_id:str
@dataclass(frozen=True,slots=True)
class DataReturn:
    value:object
@dataclass(frozen=True,slots=True)
class AgentReturn:
    agent:Agent
@dataclass(frozen=True,slots=True)
class CallResult:
    call_id:str
    owner:str
    tool:str
    value:object
@dataclass(frozen=True,slots=True)
class Transfer:
    call_id:str
    sender:str
    tool:str
    target:str
@dataclass(frozen=True,slots=True)
class CallSkipped:
    call_id:str
    owner:str
    tool:str
    reason:str='after-transfer'
@dataclass(frozen=True,slots=True)
class CallFailed:
    call_id:str
    owner:str
    tool:str
    error:str
@dataclass(frozen=True,slots=True)
class Reply:
    sender:str
    content:str
@dataclass(frozen=True,slots=True)
class BatchReport:
    owner:str
    active:Agent
    receipts:tuple[object,...]
@dataclass(frozen=True,slots=True)
class Continuation:
    session:str
    active:Agent
    history:tuple[object,...]
    request_ids:tuple[int,...]=()
@dataclass(frozen=True,slots=True)
class TransferRequest:
    call_id:str
    sender:str
    target:str
    tool:str='handoff'
@dataclass(frozen=True,slots=True)
class Note:
    sender:str
    content:str
@dataclass(frozen=True,slots=True)
class ReplayReport:
    run_id:str
    audit:tuple[object,...]
    receipts:tuple[Transfer,...]
    stopped:tuple[bool,...]
    first_stop:int|None
class ToolFailure(Exception):
    """Declared local tool failure; other programming errors remain visible."""

@dataclass(frozen=True,slots=True)
class BatchStep:
    step_id:str
    calls:tuple[ToolCall,...]
@dataclass(frozen=True,slots=True)
class ChildRun:
    step_id:str
    run:'RunNode'
@dataclass(frozen=True,slots=True)
class RunNode:
    run_id:str
    initial:str
    steps:tuple[object,...]=()
@dataclass(frozen=True,slots=True)
class OwnBatchAudit:
    step_id:str
    before:str
    after:str
    receipts:tuple[object,...]
@dataclass(frozen=True,slots=True)
class ChildAudit:
    step_id:str
    run:'RunAudit'
@dataclass(frozen=True,slots=True)
class RunAudit:
    run_id:str
    initial:str
    final:str
    history:tuple[object,...]
    steps:tuple[object,...]
