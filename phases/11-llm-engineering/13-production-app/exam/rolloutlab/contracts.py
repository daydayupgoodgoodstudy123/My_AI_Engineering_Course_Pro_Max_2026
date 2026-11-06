"""Given typed local observations, exact numeric primitives and snapshot codecs."""
from dataclasses import dataclass,asdict
from decimal import Decimal,InvalidOperation,localcontext
import copy,json
@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    template: str
    model: str="fast"
    max_output_tokens: int=1024
@dataclass(frozen=True)
class Request:
    request_id: str
    user: str
    template: str
    version: str
    query: str
    variables: dict
@dataclass(frozen=True)
class Safety:
    passed: bool
    text: str
@dataclass(frozen=True)
class Immediate:
    request_id: str
    text: str
    status: str
    cache_hit: bool
@dataclass(frozen=True)
class PreparedMiss:
    request: Request
    prompt: PromptTemplate
    rendered: str
@dataclass(frozen=True)
class RequestObservation:
    request_id: str
    user: str
    template: str
    version: str
    status: str
    cache_hit: bool
@dataclass(frozen=True)
class PaidObservation:
    request_id: str
    user: str
    experiment: str
    role: str
    version: str
    ordinal: int
    model: str
    input_tokens: int
    output_tokens: int
    cost_text: str
@dataclass(frozen=True)
class AttemptFact:
    model: str
    input_tokens: int
    output_tokens: int
    cost_text: str
@dataclass(frozen=True)
class ProviderReply:
    text: str
    attempts: tuple
class ProviderFailure(Exception):
    """Given replay adapter failure with only actually observed paid-attempt facts."""
    def __init__(self,message,attempts=()):super().__init__(message);self.attempts=attempts
@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    template: str
    control: str
    variant: str
    traffic_pct: int
    mode: str="rollout"
@dataclass(frozen=True)
class Branch:
    role: str
    version: str
    status: str
    served_text: str
    quality: object
    error: object
    attempts: tuple
@dataclass(frozen=True)
class ExperimentOutcome:
    request_id: str
    bucket: int
    served: Branch
    shadow: tuple
@dataclass(frozen=True)
class Assignment:
    user: str
    experiment_id: str
    bucket: int
@dataclass(frozen=True)
class Snapshot:
    prompts: tuple
    assignments: tuple
    observations: tuple
@dataclass(frozen=True)
class BranchDelivery:
    """Given completed branch with P3 observed-usage summary, separate display text."""
    request_id: str
    role: str
    version: str
    status: str
    served_text: str
    quality: object
    paid_usage: dict
def cost(text):
    if type(text) is not str:raise ValueError("cost spelling")
    try:value=Decimal(text)
    except InvalidOperation:raise ValueError("cost spelling")
    if not value.is_finite() or value<0:raise ValueError("cost")
    return value
def add_cost(a,b):
    with localcontext() as context:
        context.prec=max(a.adjusted(),b.adjusted())-min(a.as_tuple().exponent,b.as_tuple().exponent)+3
        return a+b
def validate_observation(row):
    if not isinstance(row,(RequestObservation,PaidObservation)):raise ValueError("observation type")
    if not row.request_id or not row.user:raise ValueError("observation identity")
    if isinstance(row,RequestObservation):
        if row.status not in ("approved","blocked_input","blocked_output","error") or type(row.cache_hit) is not bool:raise ValueError("request observation")
    else:
        if row.role not in ("served","shadow") or type(row.ordinal) is not int or row.ordinal<0:raise ValueError("attempt role")
        for value in (row.input_tokens,row.output_tokens):
            if type(value) is not int or value<0:raise ValueError("token count")
        cost(row.cost_text)
def empty_totals():
    return {"requests":0,"cache_hits":0,"status_counts":{},"paid_attempts":0,"input_tokens":0,"output_tokens":0,"cost":Decimal(0),"cost_by_user":{},"cost_by_model":{},"cost_by_role":{}}
def fold_one(totals,row):
    """Given correct source-style typed observation effect, without replay orchestration."""
    if isinstance(row,RequestObservation):
        totals["requests"]+=1;totals["cache_hits"]+=int(row.cache_hit)
        totals["status_counts"][row.status]=totals["status_counts"].get(row.status,0)+1
    else:
        totals["paid_attempts"]+=1;totals["input_tokens"]+=row.input_tokens;totals["output_tokens"]+=row.output_tokens
        value=cost(row.cost_text);totals["cost"]=add_cost(totals["cost"],value)
        for name,key in (("cost_by_user",row.user),("cost_by_model",row.model),("cost_by_role",row.role)):
            totals[name][key]=add_cost(totals[name].get(key,Decimal(0)),value)
def copy_summary(totals):return copy.deepcopy(totals)
def observation_json(row):return json.dumps({"kind":"request" if isinstance(row,RequestObservation) else "paid","fields":asdict(row)},ensure_ascii=False,separators=(",",":"))
def observation_from_json(text):
    value=json.loads(text);cls={"request":RequestObservation,"paid":PaidObservation}[value["kind"]]
    row=cls(**value["fields"]);validate_observation(row);return row
def validate_snapshot(snapshot):
    if len({(x.name,x.version) for x in snapshot.prompts})!=len(snapshot.prompts):raise ValueError("prompt identity")
    if len({(x.user,x.experiment_id) for x in snapshot.assignments})!=len(snapshot.assignments):raise ValueError("assignment identity")
    for row in snapshot.assignments:
        if type(row.bucket) is not int or not 0<=row.bucket<100:raise ValueError("bucket")
    for row in snapshot.observations:validate_observation(row)
def validate_experiment(experiment):
    if type(experiment.traffic_pct) is not int or not 0<=experiment.traffic_pct<=100 or experiment.mode not in ("rollout","shadow"):raise ValueError("experiment")
def registered_model(model,models):return type(model) is str and model in models
def validate_deployment(templates,experiments):
    """Given shapes only; identities, references and actual-model checks remain work."""
    for name,versions in templates.items():
        if not name or type(versions) is not dict:raise ValueError("template shape")
        for version,record in versions.items():
            if not version or not isinstance(record,PromptTemplate):raise ValueError("version shape")
    for name,experiment in experiments.items():
        if not name or not isinstance(experiment,Experiment):raise ValueError("experiment shape")
        validate_experiment(experiment)
