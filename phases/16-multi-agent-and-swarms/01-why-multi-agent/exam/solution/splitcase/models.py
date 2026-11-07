"""Finite local replay records; facts are declared annotations, not model claims."""
from dataclasses import dataclass
import math

def count(value, optional=False):
    if optional and value is None:return
    if type(value) is not int or value<0:raise ValueError("nonnegative integer required")

@dataclass(frozen=True)
class Fact:
    key: str
    value: str

@dataclass(frozen=True)
class Role:
    name: str
    system_prompt: str
    context_limit: int

@dataclass(frozen=True)
class Message:
    sender: str
    recipient: str
    content: str
    facts: tuple
    timestamp_us: int
    call_id: int

@dataclass(frozen=True)
class PrivateNote:
    owner: str
    content: str
    facts: tuple

@dataclass(frozen=True)
class Usage:
    call_id: int
    role: str
    input_tokens: object
    output_tokens: object
    tool_calls: int

@dataclass(frozen=True)
class CallRequest:
    call_id: int
    role: str
    system: str
    user: str
    output: str
    output_tokens: int
    tool_calls: int
    facts: tuple=()

@dataclass(frozen=True)
class Receipt:
    request: CallRequest
    usage: Usage

@dataclass(frozen=True)
class InputView:
    role: str
    user: str
    facts: tuple

@dataclass(frozen=True)
class CallSpec:
    call_id: int
    role: str
    task: str
    shared_facts: tuple
    messages: tuple
    private_notes: tuple
    output: str
    output_tokens: int
    tool_calls: int

@dataclass(frozen=True)
class Boundary:
    key: str
    role: str
    before: tuple
    forwarded: tuple
    required: tuple

@dataclass(frozen=True)
class FixedDesign:
    name: str
    roles: tuple
    calls: tuple
    boundaries: tuple=()

@dataclass(frozen=True)
class Snapshot:
    task: str
    design: FixedDesign
    reported_usage: tuple
    unit_cost: float

@dataclass(frozen=True)
class CompletedStage:
    run: str
    stage: int
    role: str
    usage: object
    before: tuple
    forwarded: tuple
    required: tuple
    status: str

@dataclass(frozen=True)
class Leaf:
    key: str
    role: str
    required: tuple=()

@dataclass(frozen=True)
class Scope:
    key: str
    shared_facts: tuple=()
    private_notes: tuple=()
    children: tuple=()

def fact_map(facts):
    values={}
    for fact in facts:
        if not isinstance(fact,Fact) or type(fact.key) is not str or not fact.key or type(fact.value) is not str:raise ValueError("fact annotation")
        if fact.key in values and values[fact.key]!=fact.value:raise ValueError("conflicting fact annotation")
        values[fact.key]=fact.value
    return values

def usage_value(usage, measured=False):
    count(usage.call_id);count(usage.tool_calls)
    count(usage.input_tokens,optional=not measured);count(usage.output_tokens,optional=not measured)
    if type(usage.role) is not str or not usage.role:raise ValueError("usage role")
    return usage

def boundary_value(boundary):
    if any(type(k) is not str or not k for seq in (boundary.before,boundary.forwarded,boundary.required) for k in seq):raise ValueError("fact id")
    if not set(boundary.forwarded)<=set(boundary.before) or not set(boundary.required)<=set(boundary.before):raise ValueError("boundary facts outside declared input")
    return boundary

def design_value(design):
    names=[role.name for role in design.roles]
    if len(set(names))!=len(names) or any(not name for name in names):raise ValueError("role identities")
    for role in design.roles:count(role.context_limit)
    ids=[]
    for call in design.calls:
        count(call.call_id);count(call.output_tokens);count(call.tool_calls);ids.append(call.call_id)
        if call.role not in names:raise ValueError("unknown role")
        fact_map(call.shared_facts)
        for message in call.messages:
            if message.recipient not in names:raise ValueError("unknown recipient")
            count(message.timestamp_us);count(message.call_id);fact_map(message.facts)
        for note in call.private_notes:
            if note.owner not in names:raise ValueError("unknown private recipient")
            fact_map(note.facts)
    if len(set(ids))!=len(ids):raise ValueError("duplicate call id")
    for boundary in design.boundaries:
        boundary_value(boundary)
        if boundary.role not in names:raise ValueError("boundary role")
    return design

def snapshot_value(snapshot):
    design_value(snapshot.design)
    if type(snapshot.task) is not str or type(snapshot.unit_cost) is not float or not math.isfinite(snapshot.unit_cost) or snapshot.unit_cost<0:raise ValueError("snapshot metadata")
    for usage in snapshot.reported_usage:usage_value(usage)
    return snapshot
