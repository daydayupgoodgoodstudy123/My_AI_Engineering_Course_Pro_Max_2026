"""Priority/coverage arbitration for original source intervals, before any scrub."""
from .contracts import validate_spans,AuditSpan,Transcript
from .legacy import apply_spans
from .fingerprint import pii_fingerprint
def resolve_overlaps(text,spans):
    """Choose nonoverlapping candidates by the declared finite greedy policy.

    Rank higher integer priority first, then longer coverage, then lower start,
    lower end, lexical kind and original input ordinal. Accept a candidate iff
    it overlaps no previously accepted interval. Adjacent half-open intervals
    do not overlap; repeated values at distinct intervals remain distinct.
    Return accepted spans in original-text order. This is priority arbitration,
    not maximum-weight interval scheduling or general PII recognition accuracy.
    Primitive bounds/type/confidence checks are supplied. Text and input spans
    remain unchanged. Reuse repaired Part 1 renderer and fingerprint helper.
    """
    values=list(spans);validate_spans(text,values)
    for span in values:
        if text[span.start:span.end]!=span.value:raise ValueError("span value")
    ranked=sorted(enumerate(values),key=lambda item:(-item[1].priority,-(item[1].end-item[1].start),item[1].start,item[1].end,item[1].kind,item[0]))
    accepted=[]
    for ordinal,span in ranked:
        if not any(span.start<other.end and other.start<span.end for other in accepted):accepted.append(span)
    return tuple(sorted(accepted,key=lambda span:(span.start,span.end)))
def scrub_overlaps(text,spans,salt):
    """Given integration of the selected original intervals with repaired Part 1."""
    selected=resolve_overlaps(text,spans)
    audits=tuple(AuditSpan(s.start,s.end,s.kind,pii_fingerprint(s.value,salt),s.confidence_text) for s in selected)
    return Transcript(text,apply_spans(text,selected),audits)
