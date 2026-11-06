"""Given finite regex fixture records, primitive checks and byte-safe local codecs."""
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
import hashlib,json,os,re
@dataclass(frozen=True)
class Recognizer:
    kind: str
    pattern: str
    priority: int
    confidence_text: str
    placeholder: str
@dataclass(frozen=True)
class Span:
    start: int
    end: int
    value: object
    kind: str
    priority: int
    confidence_text: str
    placeholder: str
@dataclass(frozen=True)
class AuditSpan:
    start: int
    end: int
    kind: str
    fingerprint: str
    confidence_text: str
@dataclass(frozen=True)
class Transcript:
    original: str
    redacted: str
    spans: tuple
@dataclass(frozen=True)
class StoredTranscript:
    redacted: str
    spans: tuple
@dataclass(frozen=True)
class GuardrailResult:
    passed: bool
    category: str
    details: str
    confidence_text: str
    latency_us: int=0
@dataclass(frozen=True)
class GuardrailReport:
    input_results: tuple=()
    output_results: tuple=()
    blocked: bool=False
    block_reason: str=""
    total_latency_us: int=0
@dataclass(frozen=True)
class Inspected:
    transcript: Transcript
    results: tuple
    blocked: bool
    delivered: str
@dataclass(frozen=True)
class Trace:
    report: GuardrailReport
    model_called: bool
    pii_scrubbed: bool
    delivered: str
    raw_output: object
    spans: tuple
    outcome: str
@dataclass(frozen=True)
class Message:
    request_id: str
    prompt: str
    replay: object
BLOCKED_INPUT="Request blocked."
BLOCKED_OUTPUT="Response blocked."
def confidence(text):
    if type(text) is not str:raise ValueError("confidence spelling")
    try:value=Decimal(text)
    except InvalidOperation:raise ValueError("confidence spelling")
    if not value.is_finite() or not 0<=value<=1:raise ValueError("confidence range")
def validate_spans(text,spans):
    for span in spans:
        if type(span.start) is not int or type(span.end) is not int or not 0<=span.start<span.end<=len(text):raise ValueError("span bounds")
        if type(span.priority) is not int or type(span.kind) is not str or not span.kind or type(span.placeholder) is not str:raise ValueError("span fields")
        confidence(span.confidence_text)
def validate_disjoint(text,spans):
    validate_spans(text,spans);end=0
    for span in spans:
        if span.start<end:raise ValueError("disjoint ordered spans required")
        end=span.end
def validate_audit(spans):
    end=0
    for span in spans:
        if type(span.start) is not int or type(span.end) is not int or not 0<=end<=span.start<span.end:raise ValueError("audit offsets")
        if not re.fullmatch(r"[0-9a-f]{12}",span.fingerprint) or not span.kind:raise ValueError("audit fields")
        confidence(span.confidence_text);end=span.end
def manifest_path(root,key):
    if type(key) is not str or not re.fullmatch(r"[A-Za-z0-9_-]+",key):raise ValueError("transcript key")
    return root/(key+".json")
def payload_bytes(text):return text.encode("utf-8")
def content_key(data):return hashlib.sha256(data).hexdigest()
def atomic_bytes(path,data):
    """Given same-directory atomic replacement, without a crash-durability claim."""
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+".tmp")
    temporary.write_bytes(data);os.replace(temporary,path)
def json_bytes(value):return json.dumps(value,ensure_ascii=False,separators=(",",":")).encode("utf-8")
def validate_report_shape(trace):
    """Given primitive shapes only; two-stage execution invariants are Part 5 work."""
    report=trace.report
    if any(type(x) is not bool for x in (report.blocked,trace.model_called,trace.pii_scrubbed)):raise ValueError("report flags")
    if type(report.total_latency_us) is not int or report.total_latency_us<0:raise ValueError("report latency")
    for results in (report.input_results,report.output_results):
        if type(results) is not tuple:raise ValueError("result sequence")
        names=[]
        for result in results:
            if type(result.passed) is not bool or not result.category or result.category in names:raise ValueError("check identity")
            names.append(result.category);confidence(result.confidence_text)
            if type(result.latency_us) is not int or result.latency_us<0:raise ValueError("check latency")
def block_reason(stage,result):return stage+" blocked: "+result.category
