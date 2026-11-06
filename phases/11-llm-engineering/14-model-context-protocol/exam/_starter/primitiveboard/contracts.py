"""Given source-shaped records, scoped identities and safe local manifest codecs."""
from dataclasses import dataclass,field,asdict
from pathlib import Path
import copy,json,os,tempfile
KINDS=("tool","resource","prompt")
@dataclass(frozen=True)
class Spec:
    kind: str
    name: str
    description: str
    handler_name: str
    uri: str=""
    input_schema: dict=field(default_factory=dict)
    arguments: tuple=()
    destructive: bool=False
@dataclass(frozen=True)
class Entry:
    spec: Spec
    handler: object
@dataclass(frozen=True)
class RegistrationChange:
    operation: str
    spec: Spec
@dataclass(frozen=True)
class ChangeView:
    kind: str
    identity: str
    operation: str
    before: object
    after: object
@dataclass(frozen=True)
class CatalogNode:
    name: str
    entries: tuple=()
    children: tuple=()
def identity(spec):return spec.uri if spec.kind=="resource" else spec.name
def slot_key(spec):return (spec.kind,identity(spec))
def validate_spec(spec):
    if not isinstance(spec,Spec) or spec.kind not in KINDS or not spec.name or not spec.handler_name:raise ValueError("primitive shape")
    if spec.kind=="resource" and not spec.uri:raise ValueError("resource URI")
    if type(spec.description) is not str or type(spec.input_schema) is not dict or type(spec.destructive) is not bool or type(spec.arguments) is not tuple or any(type(x) is not str for x in spec.arguments):raise ValueError("primitive metadata")
    json.dumps(spec.input_schema,allow_nan=False)
def copy_spec(spec):return Spec(spec.kind,spec.name,spec.description,spec.handler_name,spec.uri,copy.deepcopy(spec.input_schema),spec.arguments,spec.destructive)
def admit_entry(entry):
    """Correct registration consumer requires the declared callable contract."""
    validate_spec(entry.spec)
    if not callable(entry.handler):raise TypeError("registered primitive handler must remain callable")
    return entry
def resolve_handler(name,handlers):
    if name not in handlers or not callable(handlers[name]):raise ValueError("unavailable local handler: "+name)
    return handlers[name]
def compile_inventory(entries):
    return tuple(sorted((entry.spec.kind,identity(entry.spec),entry.spec.handler_name) for entry in entries))
def ordered_entries(entries,kind):return sorted((entry for entry in entries if entry.spec.kind==kind),key=lambda entry:identity(entry.spec))
def capabilities():return {"tools":{},"resources":{},"prompts":{}}
def complete(payload,cacheable=False):
    result={"resultType":"complete",**payload,"_meta":{"io.modelcontextprotocol/serverInfo":{"name":"local-board","version":"1.0"}}}
    if cacheable:result.update({"ttlMs":30000,"cacheScope":"private"})
    return result
def json_text(value):return json.dumps(value,ensure_ascii=False)
def validate_output(entry,output):
    if entry.spec.kind=="tool":json.dumps(output,allow_nan=False)
    elif type(output) is not str:raise ValueError("text primitive result")
def encode_spec(spec):return asdict(spec)
def decode_spec(value):
    fields=dict(value);fields["arguments"]=tuple(fields["arguments"]);spec=Spec(**fields);validate_spec(spec);return spec
def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);handle,temp=tempfile.mkstemp(dir=path.parent,prefix=".manifest-")
    try:
        with os.fdopen(handle,"wb") as stream:stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False).encode("utf-8"))
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def validate_catalog(root):
    """Given bounded local tree shape/cycle guard, not an export or namespace walker."""
    active=set()
    def visit(node):
        if not isinstance(node,CatalogNode) or not node.name:raise ValueError("catalog shape")
        if id(node) in active:raise ValueError("catalog cycle")
        active.add(id(node))
        for entry in node.entries:admit_entry(entry)
        if len({child.name for child in node.children})!=len(node.children):raise ValueError("sibling catalog names")
        for child in node.children:visit(child)
        active.remove(id(node))
    visit(root)
def scoped_admission(seen,path,entry):
    key=(path,)+slot_key(entry.spec)
    if key in seen:raise ValueError("duplicate primitive in one catalog scope")
    seen.add(key)
