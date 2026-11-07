"""Given typed local records and complete codecs, without pricing or layout algorithms."""
from dataclasses import dataclass,asdict
from fractions import Fraction
from pathlib import Path
import csv,io,json
@dataclass(frozen=True)
class LifecycleProfile:
    profile_id: str
    ttl_us: int
    min_tokens: int=0
@dataclass(frozen=True)
class Request:
    request_id: str
    profile_id: str
    prefix_key: str
    prefix_tokens: int
    suffix_tokens: int
    timestamp_us: int
@dataclass(frozen=True)
class CacheObject:
    object_id: str
    profile_id: str
    prefix_key: str
    prefix_tokens: int
    created_us: int
    expires_us: int
@dataclass(frozen=True)
class Observation:
    run_id: str
    request_id: str
    profile_id: str
    prefix_key: str
    kind: str
    object_id: object
    prefix_tokens: int
    suffix_tokens: int
    timestamp_us: int
    total_input_tokens: int
@dataclass(frozen=True)
class Lifetime:
    run_id: str
    object_id: str
    profile_id: str
    prefix_key: str
    prefix_tokens: int
    created_us: int
    observed_end_us: int
    expires_us: int
@dataclass(frozen=True)
class Collection:
    run_id: str
    report_horizon_us: int
    observations: tuple
    lifetimes: tuple
@dataclass(frozen=True)
class PriceProfile:
    profile_id: str
    base_text: str
    write_text: str
    read_text: str
    storage_per_1k_hour_text: str="0"
@dataclass(frozen=True)
class RunHeader:
    run_id: str
    report_horizon_us: int
    profile_ids: tuple
@dataclass(frozen=True)
class RunLedger:
    header: RunHeader
    observations: tuple
    lifetimes: tuple
    prices: dict
@dataclass(frozen=True)
class JournalReplay:
    records: tuple
    prices: dict
    runs: dict
@dataclass(frozen=True)
class CostReport:
    input_cost: Fraction
    storage_cost: Fraction
    total_cost: Fraction
    baseline: Fraction
    savings: Fraction
    per_profile: dict
@dataclass(frozen=True)
class AccountingEvent:
    run_id: str
    request: Observation
    new_lifetimes: tuple
@dataclass(frozen=True)
class Section:
    name: str
    stable: bool
    tokens: tuple=()
    children: tuple=()
@dataclass(frozen=True)
class PrefixPlan:
    leaf_paths: tuple
    original_variants: tuple
    cacheable_tokens: tuple
    breakpoint_path: object
    first_volatile_path: object
    shared_token_count: int
def nonnegative_integer(value):
    if type(value) is str:
        if not value or any(c not in "0123456789" for c in value):raise ValueError("integer token spelling")
        return int(value)
    if type(value) is not int or value<0:raise ValueError("nonnegative integer")
    return value
def request_fields(raw):
    for name in ("request_id","profile_id","prefix_key"):
        if type(raw[name]) is not str or (name!="prefix_key" and not raw[name]):raise ValueError("request identity")
    return raw["request_id"],raw["profile_id"],raw["prefix_key"],nonnegative_integer(raw["suffix_tokens"]),nonnegative_integer(raw["timestamp_us"])
def usage_counts(request):
    """Correct typed consumer: counts represent input usage, not currency charges."""
    total=request.prefix_tokens+request.suffix_tokens
    if type(request.prefix_tokens) is not int or request.prefix_tokens<0:raise ValueError("prefix tokens")
    return total
def prefix_identity(request):return (request.profile_id,request.prefix_key)
def object_identity(run_id,ordinal):return json.dumps([run_id,ordinal],ensure_ascii=True,separators=(",",":"))
def choose_role(request,profile,entry):
    if request.prefix_tokens<profile.min_tokens:return "UNCACHED"
    return "WRITE" if entry is None or request.timestamp_us>=entry.expires_us else "READ"
def observed_lifetime(run_id,entry,horizon):
    return Lifetime(run_id,entry.object_id,entry.profile_id,entry.prefix_key,entry.prefix_tokens,entry.created_us,min(entry.expires_us,horizon),entry.expires_us)
def validate_profiles(profiles,horizon,run_id):
    nonnegative_integer(horizon)
    if type(run_id) is not str or not run_id:raise ValueError("run identity")
    for key,p in profiles.items():
        if key!=p.profile_id or type(p.ttl_us) is not int or p.ttl_us<=0 or type(p.min_tokens) is not int or p.min_tokens<0:raise ValueError("lifecycle profile")
def rational(text):
    if type(text) is not str:raise ValueError("rate spelling")
    try:value=Fraction(text)
    except (ValueError,ZeroDivisionError):raise ValueError("rate spelling")
    if value<0:raise ValueError("negative rate")
    return value
def validate_price(price):
    for text in (price.base_text,price.write_text,price.read_text,price.storage_per_1k_hour_text):rational(text)
def validate_money(values):
    if any(not isinstance(value,Fraction) or value<0 for value in values):raise ValueError("nonnegative exact money")
def validate_record(row):
    def identity(value):
        if type(value) is not str or not value:raise ValueError("record identity")
    def integer(value):
        if type(value) is not int or value<0:raise ValueError("record integer")
    if isinstance(row,PriceProfile):
        identity(row.profile_id);validate_price(row)
    elif isinstance(row,RunHeader):
        identity(row.run_id);integer(row.report_horizon_us)
        if type(row.profile_ids) is not tuple or len(set(row.profile_ids))!=len(row.profile_ids):raise ValueError("run profile identities")
        for key in row.profile_ids:identity(key)
    elif isinstance(row,Observation):
        for value in (row.run_id,row.request_id,row.profile_id):identity(value)
        if type(row.prefix_key) is not str or row.kind not in ("WRITE","READ","UNCACHED"):raise ValueError("observation role")
        for value in (row.prefix_tokens,row.suffix_tokens,row.timestamp_us,row.total_input_tokens):integer(value)
        if row.total_input_tokens!=row.prefix_tokens+row.suffix_tokens:raise ValueError("observation counts")
        if row.kind=="UNCACHED":
            if row.object_id is not None:raise ValueError("uncached object")
        else:identity(row.object_id)
    elif isinstance(row,Lifetime):
        for value in (row.run_id,row.object_id,row.profile_id):identity(value)
        if type(row.prefix_key) is not str:raise ValueError("prefix identity")
        for value in (row.prefix_tokens,row.created_us,row.observed_end_us,row.expires_us):integer(value)
        if not row.created_us<=row.observed_end_us<=row.expires_us:raise ValueError("object interval")
    else:raise ValueError("journal record")
def encode_record(row):
    """Given complete record codec retains all raw price spellings and typed fields."""
    validate_record(row)
    return json.dumps({"kind":type(row).__name__,"fields":asdict(row)},ensure_ascii=True,separators=(",",":"))
def decode_record(text):
    value=json.loads(text);types={x.__name__:x for x in (PriceProfile,RunHeader,Observation,Lifetime)}
    if value["kind"] not in types:raise ValueError("journal record tag")
    cls=types[value["kind"]];fields=value["fields"]
    if cls is RunHeader:fields["profile_ids"]=tuple(fields["profile_ids"])
    row=cls(**fields)
    validate_record(row)
    return row
def append_encoded(path,row):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8",newline="") as stream:stream.write(encode_record(row)+"\n")
def read_encoded(path):
    path=Path(path)
    if not path.exists():return ()
    data=path.read_bytes()
    if data and not data.endswith(b"\n"):raise ValueError("incomplete journal record")
    return tuple(decode_record(line) for line in data.split(b"\n") if line)
CSV_FIELDS=("run_id","request_id","profile_id","timestamp_us","kind","prefix_key","input_cost","storage_cost","total_cost","requests","writes","reads","uncached")
def csv_line(row):
    buffer=io.StringIO(newline="");writer=csv.DictWriter(buffer,fieldnames=CSV_FIELDS,lineterminator="\n");writer.writerow(row);return buffer.getvalue()
def csv_header():
    buffer=io.StringIO(newline="");writer=csv.DictWriter(buffer,fieldnames=CSV_FIELDS,lineterminator="\n");writer.writeheader();return buffer.getvalue()
def exact_text(value):
    """Given exact rational wire spelling; denominator1 uses integer spelling."""
    return str(value.numerator) if value.denominator==1 else str(value.numerator)+"/"+str(value.denominator)
def validate_layout(root,variants):
    active=set();paths=[]
    def visit(node,parent):
        if not isinstance(node,Section) or not node.name or type(node.stable) is not bool:raise ValueError("section shape")
        if id(node) in active:raise ValueError("section cycle")
        if node.tokens and node.children:raise ValueError("section leaf or children")
        if any(type(t) is not str for t in node.tokens):raise ValueError("token fixture")
        active.add(id(node));path=parent+(node.name,)
        if node.children:
            if len({child.name for child in node.children})!=len(node.children):raise ValueError("section siblings")
            for child in node.children:visit(child,path)
        else:paths.append(path)
        active.remove(id(node))
    visit(root,())
    for variant in variants:
        if set(variant)!=set(paths) or any(type(tokens) is not tuple or any(type(t) is not str for t in tokens) for tokens in variant.values()):raise ValueError("rendered variant")
