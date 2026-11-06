"""Original-interval legacy scrubber for explicitly disjoint bounded recognizers."""
import re
from decimal import Decimal
from .contracts import Span,AuditSpan,Transcript,Inspected,GuardrailResult,BLOCKED_OUTPUT,validate_disjoint
from .fingerprint import pii_fingerprint
def matched_values(text,pattern):
    """Return the complete string of every regex match, regardless of capture groups."""
    return [match.group(0) for match in re.finditer(pattern,text)]
def collect_disjoint(text,recognizers):
    """Collect all recognizer intervals against the original text, sorted by start.

    This legacy API requires nonoverlapping matches across supplied recognizers.
    Part 3 owns overlap arbitration. Offsets are Unicode codepoints, not bytes.
    """
    spans=[]
    for recognizer in recognizers:
        working=text
        values=matched_values(working,recognizer.pattern)
        positions=list(re.finditer(recognizer.pattern,working))
        for match,value in zip(positions,values):
            spans.append(Span(match.start(),match.end(),value,recognizer.kind,recognizer.priority,recognizer.confidence_text,recognizer.placeholder))
    spans.sort(key=lambda span:(span.start,span.end))
    validate_disjoint(text,spans)
    return tuple(spans)
def apply_spans(text,spans):
    """Replace each ordered disjoint original interval, retaining all other characters."""
    validate_disjoint(text,spans)
    pieces=[];previous=0
    for span in spans:
        pieces.extend((text[previous:span.start],span.placeholder));previous=span.end
    pieces.append(text[previous:])
    return ''.join(pieces)
def allows_output(results):
    """Successful PII scrubbing can pass; every other failed output check blocks."""
    return all(result.passed or result.category=="pii_scrubbing" for result in results)
class GuardService:
    def __init__(self,recognizers,salt):self.recognizers=recognizers;self.salt=salt
    def inspect(self,text,extra_results=()):
        spans=collect_disjoint(text,self.recognizers)
        audit=tuple(AuditSpan(span.start,span.end,span.kind,pii_fingerprint(span.value,self.salt),span.confidence_text) for span in spans)
        redacted=apply_spans(text,spans)
        pii=GuardrailResult(not bool(spans),"pii_scrubbing","safe fingerprint audit",max((s.confidence_text for s in spans),key=Decimal,default="0"))
        results=tuple(extra_results)+(pii,);blocked=not allows_output(results)
        return Inspected(Transcript(text,redacted,audit),results,blocked,BLOCKED_OUTPUT if blocked else redacted)
