"""Given typed records, strict local shape helpers and complete checkpoint codecs."""
from dataclasses import dataclass,asdict
from pathlib import Path
import copy,hashlib,json,math,os
@dataclass(frozen=True)
class Checkpoint:
    thread_id: str
    checkpoint_id: str
    parent_id: object
    branch_id: str
    next_node: str
    schema_version: int
    state: dict
    reducers: dict
    def __post_init__(self):checkpoint_shape(self)
@dataclass(frozen=True)
class ForkRequest:
    thread_id: str
    from_id: str
    checkpoint_id: str
    branch_id: str
    action_name: str
@dataclass(frozen=True)
class ForkTrace:
    checkpoint: Checkpoint
    ancestry: tuple
    records: tuple
@dataclass(frozen=True)
class Worker:
    name: str
    run: object
@dataclass(frozen=True)
class StepResult:
    state: dict
    worker_updates: tuple
    completion_order: tuple
@dataclass(frozen=True)
class CommittedStep:
    parent: Checkpoint
    checkpoint: Checkpoint
    worker_updates: tuple
@dataclass(frozen=True)
class Divergence:
    thread_id: str
    common_id: object
    left_path: tuple
    right_path: tuple
    left_suffix: tuple
    right_suffix: tuple
def identity(value):
    if type(value) is not str or not value:raise ValueError("nonempty identity")
def json_shape(value,active=None):
    if value is None or type(value) in (str,int,bool):return
    if type(value) is float and math.isfinite(value):return
    if type(value) not in (list,dict):raise ValueError("finite JSON state")
    if type(value) is dict and not all(type(key) is str for key in value):raise ValueError("JSON object keys")
    active=set() if active is None else active
    if id(value) in active:raise ValueError("JSON state cycle")
    active.add(id(value))
    for item in (value if type(value) is list else value.values()):json_shape(item,active)
    active.remove(id(value))
def checkpoint_shape(row):
    if not isinstance(row,Checkpoint):raise ValueError("checkpoint")
    for value in (row.thread_id,row.checkpoint_id,row.branch_id,row.next_node):identity(value)
    if row.parent_id is not None:identity(row.parent_id)
    if row.schema_version!=1 or type(row.schema_version) is not int:raise ValueError("schema version")
    if type(row.state) is not dict or type(row.reducers) is not dict:raise ValueError("state and reducers")
    if any(type(k) is not str or v not in ("append","overwrite") for k,v in row.reducers.items()):raise ValueError("declared reducers")
    json_shape(row.state)
    if set(row.state)-set(row.reducers):raise ValueError("undeclared state field")
    for key,kind in row.reducers.items():
        if kind=="append" and key in row.state and type(row.state[key]) is not list:raise ValueError("append field")
def validate_delta(delta,reducers):
    if type(delta) is not dict or set(delta)-set(reducers):raise ValueError("declared update fields")
    json_shape(delta)
    for key,value in delta.items():
        if reducers[key]=="append" and type(value) is not list:raise ValueError("append update")
def checkpoint_key(row):return (row.thread_id,row.checkpoint_id)
def pop_pending(state,action_name):
    """Correct consumer removes one explicitly selected pending local action payload."""
    return state["pending"].pop(action_name)
def validate_records(records):
    keys=set()
    for row in records:
        if not isinstance(row,Checkpoint):raise ValueError("typed checkpoint")
        key=checkpoint_key(row)
        if key in keys:raise ValueError("duplicate checkpoint")
        keys.add(key)
    for row in records:
        if row.parent_id is not None and (row.thread_id,row.parent_id) not in keys:raise ValueError("missing scoped parent")
def index_records(records):
    """Given full typed/identity/parent validation and one retained scoped index.

    This is the complete catalog preparation used by MemoryBook. The original
    validate_records remains available unchanged to other local components.
    All supplied records are checked; no path or record is discarded.
    """
    index={}
    for row in records:
        if not isinstance(row,Checkpoint):raise ValueError("typed checkpoint")
        key=checkpoint_key(row)
        if key in index:raise ValueError("duplicate checkpoint")
        index[key]=row
    for row in records:
        if row.parent_id is not None and (row.thread_id,row.parent_id) not in index:raise ValueError("missing scoped parent")
    return index
def complete_checkpoint(row):
    checkpoint_shape(row)
    return asdict(row)
def restore_checkpoint(value):
    row=Checkpoint(**value);checkpoint_shape(row);return row
def artifact_path(root,key):
    spelling=json.dumps(list(key),ensure_ascii=True,separators=(",",":"));return Path(root)/"states"/(hashlib.sha256(spelling.encode("utf-8")).hexdigest()+".json")
def write_artifact(path,row):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(".tmp")
    text=json.dumps(complete_checkpoint(row),ensure_ascii=True,separators=(",",":"),allow_nan=False)
    try:
        temporary.write_text(text,encoding="utf-8");os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()
def read_artifact(path):return restore_checkpoint(json.loads(Path(path).read_text(encoding="utf-8")))
def append_index(root,key):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/"lineage.index").open("a",encoding="utf-8",newline="") as stream:stream.write(json.dumps(list(key),ensure_ascii=True)+"\n")
def read_index(root):
    path=Path(root)/"lineage.index"
    if not path.exists():return ()
    data=path.read_bytes()
    if data and not data.endswith(b"\n"):raise ValueError("incomplete index")
    return tuple(tuple(json.loads(line)) for line in data.split(b"\n") if line)
def line_json(value):return json.dumps(value,ensure_ascii=True,separators=(",",":"),allow_nan=False)+"\n"
def committed_pair(parent,checkpoint):
    if parent.thread_id!=checkpoint.thread_id or checkpoint.parent_id!=parent.checkpoint_id:raise ValueError("exact committed parent")
    checkpoint_shape(parent);checkpoint_shape(checkpoint)
    if set(parent.state)-set(checkpoint.state):raise ValueError("bounded patch does not remove fields")
def validate_lineage(records):
    validate_records(records);index={checkpoint_key(row):row for row in records}
    for row in records:
        seen=set();current=row
        while current is not None:
            key=checkpoint_key(current)
            if key in seen:raise ValueError("checkpoint cycle")
            seen.add(key);current=index.get((current.thread_id,current.parent_id)) if current.parent_id is not None else None
    return index
